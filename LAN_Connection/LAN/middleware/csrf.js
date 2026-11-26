const { csrfSync } = require('csrf-sync');

const {
    generateToken,
    csrfSynchronisedProtection
} = csrfSync({
    getTokenFromRequest: (req) => req.body?.CSRFToken
});

module.exports = {
    generateToken,
    csrfSynchronisedProtection
};
