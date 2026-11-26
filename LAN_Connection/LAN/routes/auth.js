const express = require('express');
const bcrypt = require('bcrypt');
const { rateLimit } = require('express-rate-limit');
const db = require('../database');

const router = express.Router();

// Limit login attempts to 20 requests per IP per minute.
const loginLimiter = rateLimit({
    windowMs: 60 * 1000,
    limit: 20,
    standardHeaders: true,
    legacyHeaders: false,

    handler: (req, res) => {
        res.status(429).render('login', {
            error: 'Έγιναν πολλές προσπάθειες σύνδεσης. Περίμενε ένα λεπτό και δοκίμασε ξανά.'
        });
    }
});

router.get('/login', (req, res) => {
    if (req.session.user) {
	if (req.session.user.role === 'admin') {
	    return res.redirect('/admin');
	}

	if (req.session.user.role === 'safety_admin') {
	    return res.redirect('/safety-zone');
	}

	return res.redirect('/dashboard');
    }

    res.render('login', { error: null });
});

router.post('/login', loginLimiter, async (req, res, next) => {
    try {
        const username = String(req.body.username || '').trim();
        const password = String(req.body.password || '');

        if (
            username.length === 0 ||
            username.length > 50 ||
            password.length === 0 ||
            password.length > 200
        ) {
            return res.status(400).render('login', {
                error: 'Μη έγκυρο username ή password.'
            });
        }

        const user = db.prepare(`
            SELECT id, username, password_hash, role, active
            FROM users
            WHERE username = ?
        `).get(username);

        if (
            !user ||
            user.active !== 1 ||
            !(await bcrypt.compare(password, user.password_hash))
        ) {
            return res.status(401).render('login', {
                error: 'Λανθασμένο username ή password.'
            });
        }

        req.session.regenerate((err) => {
            if (err) {
                return next(err);
            }

// Αποθήκευση του συνδεδεμένου χρήστη στο session
    req.session.user = {
        id: user.id,
        username: user.username,
        role: user.role
    };


req.session.save((saveErr) => {
    if (saveErr) {
        return next(saveErr);
    }

    if (user.role === 'admin') {
        return res.redirect('/admin');
    }

    if (user.role === 'safety_admin') {
        return res.redirect('/safety-zone');
    }

    return res.redirect('/dashboard');
});


        });
    } catch (error) {
        next(error);
    }
});

router.post('/logout', (req, res, next) => {
    req.session.destroy((err) => {
        if (err) {
            return next(err);
        }

        res.clearCookie('lan_video_session', {
            httpOnly: true,
            sameSite: 'strict',
            secure: false
        });

        res.redirect('/login');
    });
});

module.exports = router;
