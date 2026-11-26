const express = require('express');
const fs = require('fs');
const path = require('path');

const router = express.Router();
const db = require('../database');

const { requireLogin, requireRole } = require('../middleware/auth');

const {
    beginWipe,
    cancelActiveUploads
} = require('../middleware/emergency');

const uploadsDirectory = path.join(__dirname, '..', 'uploads');

function freezeUploads() {
    db.prepare(`
        INSERT INTO app_settings (key, value, updated_at)
        VALUES ('uploads_frozen', '1', CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = '1',
            updated_at = CURRENT_TIMESTAMP
    `).run();
}

router.get(
    '/safety-zone',
    requireLogin,
    requireRole('safety_admin'),
    (req, res, next) => {
        try {
            const setting = db.prepare(`
                SELECT value
                FROM app_settings
                WHERE key = 'uploads_frozen'
            `).get();

            res.render('safety', {
                user: req.session.user,
                uploadsFrozen: setting?.value === '1'
            });
        } catch (error) {
            next(error);
        }
    }
);

router.post(
    '/safety-zone/freeze',
    requireLogin,
    requireRole('safety_admin'),
    (req, res, next) => {
        try {
            freezeUploads();
            res.redirect('/safety-zone');
        } catch (error) {
            next(error);
        }
    }
);

router.post(
    '/safety-zone/unfreeze',
    requireLogin,
    requireRole('safety_admin'),
    (req, res, next) => {
        try {
            db.prepare(`
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('uploads_frozen', '0', CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = '0',
                    updated_at = CURRENT_TIMESTAMP
            `).run();

            res.redirect('/safety-zone');
        } catch (error) {
            next(error);
        }
    }
);

router.post(
    '/safety-zone/emergency-wipe',
    requireLogin,
    requireRole('safety_admin'),
    async (req, res) => {
        if (!beginWipe()) {
            return res.status(409).send(
                'Ένα Emergency Wipe βρίσκεται ήδη σε εξέλιξη.'
            );
        }

        try {
            // Πρώτα παγώνουμε μόνιμα τις μεταφορτώσεις.
            freezeUploads();

            // Ακυρώνουμε και περιμένουμε τις ενεργές μεταφορτώσεις.
            await cancelActiveUploads();

            // Διαγράφουμε τα αρχεία πριν τις εγγραφές της βάσης.
            const entries = await fs.promises.readdir(
                uploadsDirectory,
                { withFileTypes: true }
            );

            for (const entry of entries) {
                if (!entry.isFile()) {
                    throw new Error(
                        `Μη αναμενόμενο στοιχείο στον φάκελο uploads: ${entry.name}`
                    );
                }

                await fs.promises.unlink(
                    path.join(uploadsDirectory, entry.name)
                );
            }

            // Οι εγγραφές διαγράφονται μόνο αφού διαγραφούν τα αρχεία.
            const deleteSubmissions = db.transaction(() => {
                db.prepare('DELETE FROM submissions').run();
            });

            deleteSubmissions();

            console.info(
                '[EMERGENCY WIPE] Επιτυχία: διαγράφηκαν όλα τα αρχεία και οι υποβολές.'
            );

            return res.send(
                'Το Emergency Wipe ολοκληρώθηκε. Οι μεταφορτώσεις παραμένουν παγωμένες.'
            );
        } catch (error) {
            console.error('[EMERGENCY WIPE] ΑΠΟΤΥΧΙΑ:', error);

            return res.status(500).send(
                'Το Emergency Wipe απέτυχε. Οι μεταφορτώσεις παραμένουν παγωμένες. Έλεγξε το terminal για το σφάλμα.'
            );
        }
    }
);

module.exports = router;
