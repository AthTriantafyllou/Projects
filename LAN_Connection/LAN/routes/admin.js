const express = require('express');
const { requireLogin, requireRole } = require('../middleware/auth');
const db = require('../database');
const bcrypt = require('bcrypt');

const archiver = require('archiver');
const fs = require('fs');
const path = require('path');


const router = express.Router();

// Admin dashboard: λίστα εκκρεμών υποβολών
router.get(
    '/admin',
    requireLogin,
    requireRole('admin'),
    (req, res, next) => {
        try {
            const pendingCount = db.prepare(`
                SELECT COUNT(*) AS count
                FROM submissions
                WHERE status = 'pending'
            `).get().count;


const selectedUser = req.query.user || '';

const users = db.prepare(`
    SELECT id, username
    FROM users
    WHERE role = 'user'
    ORDER BY username ASC
`).all();

let submissions;

if (selectedUser === '') {
    submissions = db.prepare(`
        SELECT
            s.id,
            s.user_id,
            u.username,
            s.category,
            s.description,
            s.event_time,
            s.original_filename,
            s.file_size,
            s.created_at
        FROM submissions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.status = 'pending'
        ORDER BY s.created_at ASC, s.id ASC
    `).all();
} else {
    const userId = Number(selectedUser);

    if (!Number.isSafeInteger(userId) || userId <= 0) {
        return res.status(400).send('Μη έγκυρη επιλογή χρήστη.');
    }

    const userExists = users.some((user) => user.id === userId);

    if (!userExists) {
        return res.status(400).send('Ο χρήστης δεν βρέθηκε.');
    }

    submissions = db.prepare(`
        SELECT
            s.id,
            s.user_id,
            u.username,
            s.category,
            s.description,
            s.event_time,
            s.original_filename,
            s.file_size,
            s.created_at
        FROM submissions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.status = 'pending'
          AND s.user_id = ?
        ORDER BY s.created_at ASC, s.id ASC
    `).all(userId);
}


res.render('admin', {
    user: req.session.user,
    pendingCount,
    submissions,
    users,
    selectedUser
});




        } catch (error) {
            next(error);
        }
    }
);



// Λήψη υποβολής σε ZIP: βίντεο + metadata
router.get(
    '/admin/submissions/:id/download',
    requireLogin,
    requireRole('admin'),
    (req, res, next) => {
        const submissionId = Number(req.params.id);

        if (!Number.isSafeInteger(submissionId) || submissionId <= 0) {
            return res.status(400).send('Μη έγκυρος αριθμός υποβολής.');
        }

        try {
            const submission = db.prepare(`
                SELECT
                    s.id,
                    s.category,
                    s.description,
                    s.event_time,
                    s.stored_filename,
                    s.original_filename,
                    s.file_size,
                    s.created_at,
                    u.username
                FROM submissions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.id = ?
                  AND s.status = 'pending'
            `).get(submissionId);

            if (!submission) {
                return res.status(404).send('Η υποβολή δεν βρέθηκε.');
            }

            const uploadDirectory = path.join(__dirname, '..', 'uploads');
            const videoPath = path.join(
                uploadDirectory,
                submission.stored_filename
            );

            if (
                path.dirname(videoPath) !== uploadDirectory ||
                !fs.existsSync(videoPath)
            ) {
                return res.status(404).send('Το αρχείο βίντεο δεν βρέθηκε.');
            }

            const metadata = [
                `ID υποβολής: ${submission.id}`,
                `Χρήστης: ${submission.username}`,
                `Κατηγορία: ${submission.category}`,
                `Περιγραφή: ${submission.description}`,
                `Ημερομηνία συμβάντος: ${submission.event_time || 'Δεν δηλώθηκε'}`,
                `Ημερομηνία υποβολής: ${submission.created_at}`,
                `Αρχικό όνομα αρχείου: ${submission.original_filename}`,
                `Μέγεθος αρχείου: ${submission.file_size} bytes`
            ].join('\n');

            res.status(200);
            res.setHeader(
                'Content-Type',
                'application/zip'
            );
            res.setHeader(
                'Content-Disposition',
                `attachment; filename="submission_${submission.id}.zip"`
            );


const archive = new archiver.ZipArchive({
    zlib: { level: 1 }
});


            archive.on('warning', (error) => {
                if (error.code === 'ENOENT') {
                    console.error('Προειδοποίηση δημιουργίας ZIP:', error);
                } else {
                    next(error);
                }
            });

            archive.on('error', (error) => {
                console.error('Αποτυχία δημιουργίας ZIP:', error);
                if (!res.headersSent) {
                    next(error);
                } else {
                    res.destroy(error);
                }
            });

            archive.pipe(res);

            archive.file(videoPath, {
                name: 'video' + path.extname(submission.stored_filename)
            });

            archive.append(metadata, {
                name: 'infos.txt'
            });

            archive.finalize();
        } catch (error) {
            next(error);
        }
    }
);



// Διαγραφή υποβολής από τον admin
router.post(
    '/admin/submissions/:id/delete',
    requireLogin,
    requireRole('admin'),
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
                  AND status = 'pending'
            `).get(submissionId);

            if (!submission) {
                return res.status(404).send(
                    'Η υποβολή δεν βρέθηκε ή έχει ήδη διαγραφεί.'
                );
            }

            // Σημειώνουμε την υποβολή ως διαγραμμένη στη βάση.
            const result = db.prepare(`
                UPDATE submissions
                SET status = 'deleted'
                WHERE id = ?
                  AND status = 'pending'
            `).run(submissionId);

            if (result.changes !== 1) {
                return res.status(409).send(
                    'Η υποβολή έχει ήδη διαγραφεί ή άλλαξε κατάσταση.'
                );
            }

            // Διαγράφουμε το αντίστοιχο βίντεο από το uploads.
            const uploadDirectory = path.resolve(__dirname, '..', 'uploads');
            const videoPath = path.resolve(
                uploadDirectory,
                submission.stored_filename
            );

            if (path.dirname(videoPath) !== uploadDirectory) {
                console.error(
                    'Μη έγκυρη διαδρομή αρχείου για την υποβολή:',
                    submissionId
                );

                return res.status(500).send(
                    'Η υποβολή σημειώθηκε ως διαγραμμένη, αλλά χρειάζεται έλεγχος του αρχείου.'
                );
            }

            fs.unlink(videoPath, (error) => {
                if (error && error.code !== 'ENOENT') {
                    console.error(
                        'Αποτυχία διαγραφής βίντεο:',
                        submissionId,
                        error
                    );

                    return res.status(500).send(
                        'Η υποβολή σημειώθηκε ως διαγραμμένη, αλλά το βίντεο δεν διαγράφηκε. Χρειάζεται έλεγχος.'
                    );
                }

                return res.redirect('/admin');
            });
        } catch (error) {
            next(error);
        }
    }
);


// Users Manager: επιστροφή λίστας χρηστών μόνο για admin
router.get(
    '/admin/users',
    requireLogin,
    requireRole('admin'),
    (req, res, next) => {
        try {
            const users = db.prepare(`
                SELECT
                    id,
                    username,
                    role,
                    active,
                    created_at
                FROM users
                ORDER BY
                    CASE role
                        WHEN 'admin' THEN 1
                        WHEN 'safety_admin' THEN 2
                        ELSE 3
                    END,
                    username ASC
            `).all();

            return res.json({ users });
        } catch (error) {
            next(error);
        }
    }
);



// Users Manager: δημιουργία χρήστη
router.post(
    '/admin/users/create',
    requireLogin,
    requireRole('admin'),
    async (req, res, next) => {
        try {
            const username = String(req.body.username || '').trim();
            const password = String(req.body.password || '');
            const role = String(req.body.role || '');

            const allowedRoles = ['user', 'admin', 'safety_admin'];

            if (
                username.length < 3 ||
                username.length > 50 ||
                !/^[a-zA-Z0-9_-]+$/.test(username)
            ) {
                return res.status(400).json({
                    error: 'Το username πρέπει να έχει 3–50 χαρακτήρες και να περιέχει μόνο λατινικά γράμματα, αριθμούς, _ ή -.'
                });
            }

            if (password.length < 3 || password.length > 200) {
                return res.status(400).json({
                    error: 'Το password πρέπει να έχει τουλάχιστον 3 χαρακτήρες και έως 200.'
                });
            }

            if (!allowedRoles.includes(role)) {
                return res.status(400).json({
                    error: 'Μη έγκυρος ρόλος χρήστη.'
                });
            }

            const existingUser = db.prepare(`
                SELECT id FROM users WHERE username = ?
            `).get(username);

            if (existingUser) {
                return res.status(409).json({
                    error: 'Το username χρησιμοποιείται ήδη.'
                });
            }

            const passwordHash = await bcrypt.hash(password, 12);

            const result = db.prepare(`
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            `).run(username, passwordHash, role);

            return res.status(201).json({
                message: 'Ο χρήστης δημιουργήθηκε επιτυχώς.',
                user: {
                    id: Number(result.lastInsertRowid),
                    username,
                    role,
                    active: 1
                }
            });
        } catch (error) {
            if (error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
                return res.status(409).json({
                    error: 'Το username χρησιμοποιείται ήδη.'
                });
            }

            next(error);
        }
    }
);


// Users Manager: επεξεργασία χρήστη
router.post(
    '/admin/users/:id/edit',
    requireLogin,
    requireRole('admin'),
    async (req, res, next) => {
        try {
            const userId = Number(req.params.id);
            const username = String(req.body.username || '').trim();
            const role = String(req.body.role || '');
            const password = String(req.body.password || '');

            const allowedRoles = ['user', 'admin', 'safety_admin'];

            if (!Number.isSafeInteger(userId) || userId <= 0) {
                return res.status(400).json({
                    error: 'Μη έγκυρο ID χρήστη.'
                });
            }

            if (
                username.length < 3 ||
                username.length > 50 ||
                !/^[a-zA-Z0-9_-]+$/.test(username)
            ) {
                return res.status(400).json({
                    error: 'Το username πρέπει να έχει 3–50 χαρακτήρες και να περιέχει μόνο λατινικά γράμματα, αριθμούς, _ ή -.'
                });
            }

            if (!allowedRoles.includes(role)) {
                return res.status(400).json({
                    error: 'Μη έγκυρος ρόλος χρήστη.'
                });
            }

            if (password && (password.length < 3 || password.length > 200)) {
                return res.status(400).json({
                    error: 'Το νέο password πρέπει να έχει τουλάχιστον 3 χαρακτήρες και έως 200.'
                });
            }

            const existingUser = db.prepare(`
                SELECT id, username, role
                FROM users
                WHERE id = ?
            `).get(userId);

            if (!existingUser) {
                return res.status(404).json({
                    error: 'Ο χρήστης δεν βρέθηκε.'
                });
            }

            // Δεν επιτρέπουμε αλλαγή username ή ρόλου
            // του λογαριασμού που χρησιμοποιείται αυτή τη στιγμή.
            if (userId === req.session.user.id) {
                if (
                    username !== existingUser.username ||
                    role !== existingUser.role
                ) {
                    return res.status(403).json({
                        error: 'Δεν επιτρέπεται να αλλάξεις το username ή τον ρόλο του λογαριασμού με τον οποίο είσαι συνδεδεμένος.'
                    });
                }
            }

            const duplicateUser = db.prepare(`
                SELECT id
                FROM users
                WHERE username = ? AND id != ?
            `).get(username, userId);

            if (duplicateUser) {
                return res.status(409).json({
                    error: 'Το username χρησιμοποιείται ήδη.'
                });
            }

            if (password) {
                const passwordHash = await bcrypt.hash(password, 12);

                db.prepare(`
                    UPDATE users
                    SET username = ?, role = ?, password_hash = ?
                    WHERE id = ?
                `).run(username, role, passwordHash, userId);
            } else {
                db.prepare(`
                    UPDATE users
                    SET username = ?, role = ?
                    WHERE id = ?
                `).run(username, role, userId);
            }

            return res.json({
                message: 'Ο χρήστης ενημερώθηκε επιτυχώς.'
            });
        } catch (error) {
            if (error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
                return res.status(409).json({
                    error: 'Το username χρησιμοποιείται ήδη.'
                });
            }

            next(error);
        }
    }
);



// Users Manager: διαγραφή χρήστη
router.post(
    '/admin/users/:id/delete',
    requireLogin,
    requireRole('admin'),
    (req, res, next) => {
        try {
            const userId = Number(req.params.id);

            if (!Number.isSafeInteger(userId) || userId <= 0) {
                return res.status(400).json({
                    error: 'Μη έγκυρο ID χρήστη.'
                });
            }

            if (userId === req.session.user.id) {
                return res.status(403).json({
                    error: 'Δεν μπορείς να διαγράψεις τον λογαριασμό με τον οποίο είσαι συνδεδεμένος.'
                });
            }

            const user = db.prepare(`
                SELECT id, username, role
                FROM users
                WHERE id = ?
            `).get(userId);

            if (!user) {
                return res.status(404).json({
                    error: 'Ο χρήστης δεν βρέθηκε.'
                });
            }

            // Επιτρέπεται διαγραφή μόνο σε απλούς χρήστες.
            if (user.role !== 'user') {
                return res.status(403).json({
                    error: 'Μπορούν να διαγραφούν μόνο λογαριασμοί User.'
                });
            }

            // Πρόσθετη προστασία του λογαριασμού safety.
            if (user.username.toLowerCase() === 'safety') {
                return res.status(403).json({
                    error: 'Ο λογαριασμός safety προστατεύεται από διαγραφή.'
                });
            }

            db.prepare(`
                DELETE FROM users
                WHERE id = ?
            `).run(userId);

            return res.json({
                message: 'Ο χρήστης διαγράφηκε επιτυχώς.'
            });
        } catch (error) {
            if (
                error.code === 'SQLITE_CONSTRAINT_FOREIGNKEY' ||
                error.code === 'SQLITE_CONSTRAINT_TRIGGER'
            ) {
                return res.status(409).json({
                    error: 'Ο χρήστης έχει υποβολές. Διέγραψε πρώτα τις υποβολές του και δοκίμασε ξανά.'
                });
            }

            next(error);
        }
    }
);


module.exports = router;
