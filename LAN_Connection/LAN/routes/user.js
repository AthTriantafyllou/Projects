const express = require('express');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const multer = require('multer');
const rateLimit = require('express-rate-limit');

const { requireLogin, requireRole } = require('../middleware/auth');
const db = require('../database');

const {
    upload,
    checkDiskSpace,
    validateVideoFile,
    deleteTemporaryUpload
} = require('../middleware/upload');

const { validateSubmission } = require('../middleware/validation');

const {
    csrfSynchronisedProtection
} = require('../middleware/csrf');

const router = express.Router();

const {
    isWipeInProgress,
    registerUpload
} = require('../middleware/emergency');

// Μέγιστο 5 αιτήματα upload ανά IP ανά λεπτό
const uploadIpLimiter = rateLimit({
    windowMs: 60 * 1000,
    limit: 5,
    standardHeaders: true,
    legacyHeaders: false,
    message: 'Έχουν γίνει πολλές προσπάθειες. Περίμενε ένα λεπτό.'
});

// Μέγιστο 5 uploads ανά χρήστη ανά 24 ώρες
const uploadUserLimiter = rateLimit({
    windowMs: 24 * 60 * 60 * 1000,
    limit: 5,
    keyGenerator: (req) => String(req.session.user.id),
    standardHeaders: true,
    legacyHeaders: false,
    message: 'Έχεις συμπληρώσει το ημερήσιο όριο των 5 μεταφορτώσεων.'
});


const uploadDirectory = path.join(__dirname, '..', 'uploads');

// Αρχική σελίδα
router.get('/dashboard', requireLogin, (req, res) => {
    res.render('dashboard', {
        user: req.session.user
    });
});

// Ιστορικό προσωπικών υποβολών
router.get(
    '/history',
    requireLogin,
    requireRole('user'),
    (req, res, next) => {
        try {
            const submissions = db.prepare(`
                SELECT
                    id,
                    category,
                    description,
                    event_time,
                    status,
                    created_at
                FROM submissions
                WHERE user_id = ?
                  AND status != 'deleted'
                ORDER BY created_at DESC, id DESC
            `).all(req.session.user.id);

            res.render('history', {
                user: req.session.user,
                submissions
            });
        } catch (error) {
            next(error);
        }
    }
);

// Εμφάνιση φόρμας υποβολής
router.get(
    '/upload',
    requireLogin,
    requireRole('user'),
    (req, res) => {
        res.render('upload', {
            user: req.session.user,
            error: null
        });
    }
);



function receiveUpload(req, res, next) {
    let resolveDone;

    const done = new Promise((resolve) => {
        resolveDone = resolve;
    });

    const uploadState = {
        cancelled: false,
        done,

        cancel() {
            this.cancelled = true;

            if (!req.destroyed) {
                req.destroy();
            }


        }
    };

    req.uploadState = uploadState;

    let released = false;
    const unregisterUpload = registerUpload(uploadState);

    function release() {
        if (released) return;
        released = true;
        unregisterUpload();
        resolveDone();
    }

    res.once('finish', release);

    req.once('aborted', () => {
        uploadState.cancelled = true;
    });

    upload.single('video')(req, res, async (error) => {
        if (error) {
            await deleteTemporaryUpload(req);

            if (res.destroyed || res.headersSent) {
                release();
                return;
            }

            if (error instanceof multer.MulterError) {
                const tooLarge = error.code === 'LIMIT_FILE_SIZE';

                release();

                return res.status(tooLarge ? 413 : 400).render('upload', {
                    user: req.session.user,
                    error: tooLarge
                        ? 'Το βίντεο ξεπερνά το μέγιστο επιτρεπόμενο μέγεθος των 200 MB.'
                        : 'Το αρχείο ή τα δεδομένα της φόρμας δεν είναι έγκυρα.'
                });
            }

            release();
            return next(error);
        }

        if (uploadState.cancelled || isWipeInProgress()) {
            await deleteTemporaryUpload(req);
            release();
            return;
        }

        next();
    });
}




// Έλεγχος CSRF μετά την ανάγνωση της multipart φόρμας
function protectUploadWithCsrf(req, res, next) {
    csrfSynchronisedProtection(req, res, async (error) => {
        if (error) {
            await deleteTemporaryUpload(req);
            return next(error);
        }

        next();
    });
}



function checkUploadsFrozen(req, res, next) {
    try {
        if (isWipeInProgress()) {
            return res.status(503).send(
                'Εκτελείται Emergency Wipe. Οι μεταφορτώσεις δεν επιτρέπονται.'
            );
        }

        const setting = db.prepare(`
            SELECT value
            FROM app_settings
            WHERE key = 'uploads_frozen'
        `).get();

        if (setting && setting.value === '1') {
            return res.status(503).send(
                'Οι μεταφορτώσεις έχουν προσωρινά παγώσει από τον διαχειριστή ασφαλείας. Δοκίμασε ξανά αργότερα.'
            );
        }

        next();
    } catch (error) {
        console.error('Αποτυχία ελέγχου Emergency Freeze:', error);

        return res.status(503).send(
            'Δεν είναι δυνατή η επιβεβαίωση της κατάστασης ασφαλείας. Η μεταφόρτωση δεν επιτρέπεται αυτή τη στιγμή.'
        );
    }
}



// Υποβολή βίντεο
router.post(
    '/upload',
	uploadIpLimiter,
    requireLogin,
    requireRole('user'),
	checkUploadsFrozen,
	uploadUserLimiter,
    checkDiskSpace,
    receiveUpload,
    protectUploadWithCsrf,
    validateVideoFile,
    validateSubmission,
    async (req, res, next) => {
        let finalPath;

        try {
            const { category, description, event_time } =
                req.validatedSubmission;

            const extension = req.detectedVideoType.ext;

            const storedFilename =
                `${crypto.randomBytes(32).toString('hex')}.${extension}`;

            finalPath = path.join(uploadDirectory, storedFilename);

            const originalFilename = path.basename(
                req.file.originalname.replace(/\\/g, '/')
            ).replace(/[\r\n\0]/g, '').slice(0, 255) || 'video';



// Μην επιτρέψεις αποθήκευση αν ξεκίνησε Emergency Wipe.
if (req.uploadState?.cancelled || isWipeInProgress()) {
    await deleteTemporaryUpload(req);
    return;
}

// Μεταφορά από προσωρινό σε τελικό τυχαίο όνομα
await fs.promises.rename(req.file.path, finalPath);

// Επανέλεγχος μετά τη μεταφορά του αρχείου.
if (req.uploadState?.cancelled || isWipeInProgress()) {
    await fs.promises.unlink(finalPath).catch(() => {});
    finalPath = undefined;
    return;
}



            try {
                db.prepare(`
                    INSERT INTO submissions (
                        user_id,
                        category,
                        description,
                        event_time,
                        stored_filename,
                        original_filename,
                        file_size
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                `).run(
                    req.session.user.id,
                    category,
                    description,
                    event_time,
                    storedFilename,
                    originalFilename,
                    req.file.size
                );
            } catch (databaseError) {
                await fs.promises.unlink(finalPath).catch(() => {});
                throw databaseError;
            }

            return res.redirect('/history');
        } catch (error) {
            await deleteTemporaryUpload(req);

            if (finalPath) {
                await fs.promises.unlink(finalPath).catch(() => {});
            }

            next(error);
        }
    }
);



/* Διαγραφή προσωπικής εκκρεμούς υποβολής */
router.post(
    '/history/:id/delete',
    requireLogin,
    requireRole('user'),
    (req, res, next) => {
        const submissionId = Number(req.params.id);

        if (!Number.isSafeInteger(submissionId) || submissionId <= 0) {
            return res.status(400).send('Μη έγκυρος αριθμός υποβολής.');
        }

        try {
            const submission = db.prepare(`
                SELECT id, stored_filename
                FROM submissions
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'pending'
            `).get(submissionId, req.session.user.id);

            if (!submission) {
                return res.status(404).send(
                    'Η υποβολή δεν βρέθηκε ή δεν μπορεί πλέον να διαγραφεί.'
                );
            }

            const result = db.prepare(`
                UPDATE submissions
                SET status = 'deleted'
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'pending'
            `).run(submissionId, req.session.user.id);

            if (result.changes !== 1) {
                return res.status(409).send(
                    'Η υποβολή άλλαξε κατάσταση. Ανανεώστε το ιστορικό.'
                );
            }

            const filePath = path.join(
                uploadDirectory,
                submission.stored_filename
            );

            fs.promises.unlink(filePath).catch((error) => {
                if (error.code !== 'ENOENT') {
                    console.error(
                        'Αποτυχία διαγραφής αρχείου υποβολής:',
                        submission.id,
                        error
                    );
                }
            });

            return res.redirect('/history');
        } catch (error) {
            next(error);
        }
    }
);


module.exports = router;
