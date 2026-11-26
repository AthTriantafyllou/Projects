require('dotenv').config();

const express = require('express');
const session = require('express-session');
const path = require('path');

const {
    generateToken,
    csrfSynchronisedProtection
} = require('./middleware/csrf');

const app = express();
const PORT = 3000;

if (!process.env.SESSION_SECRET) {
    console.error('Missing SESSION_SECRET in .env');
    process.exit(1);
}



app.disable('x-powered-by');

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.static(path.join(__dirname, 'public')));

app.use(express.urlencoded({
    extended: false,
    limit: '10kb'
}));

app.use(session({
    name: 'lan_video_session',
    secret: process.env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
        httpOnly: true,
        sameSite: 'strict',
        secure: false,
        maxAge: 60 * 60 * 1000
    }
}));

app.use((req, res, next) => {
    res.locals.csrfToken = generateToken(req);
    next();
});



app.use((req, res, next) => {
    if (req.method === 'POST' && req.path === '/upload') {
        return next();
    }

    csrfSynchronisedProtection(req, res, next);
});


app.get('/', (req, res) => {
    res.redirect('/login');
});

app.use('/', require('./routes/auth'));
app.use('/', require('./routes/user'));
app.use('/', require('./routes/admin'));
app.use('/', require('./routes/safety'));


app.use((err, req, res, next) => {
    if (err.code === 'EBADCSRFTOKEN') {
        return res.status(403).send(
            'Η φόρμα δεν είναι έγκυρη ή έχει λήξει. Ανανεώστε τη σελίδα και δοκιμάστε ξανά.'
        );
    }

    console.error(err);

    res.status(500).send('Παρουσιάστηκε εσωτερικό σφάλμα.');
});

app.listen(PORT, '127.0.0.1', () => {
    console.log(`LAN Video Manager running at http://127.0.0.1:${PORT}`);
});
