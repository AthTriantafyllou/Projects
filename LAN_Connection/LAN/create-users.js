const readline = require('readline');
const bcrypt = require('bcrypt');
const db = require('./database');

const users = [
    { username: 'ef5', role: 'user' },
    { username: 'ef6', role: 'user' },
    { username: 'ef8', role: 'user' },
    { username: 'ef9', role: 'user' },
    { username: 'admin', role: 'admin' },
    { username: 'safety', role: 'safety_admin' }
];

function askHidden(question) {
    return new Promise((resolve, reject) => {
        if (!process.stdin.isTTY || !process.stdout.isTTY) {
            reject(new Error('Run this script directly in a terminal.'));
            return;
        }

        process.stdout.write(question);

        let password = '';

        const onData = (key) => {
            if (key === '\u0003') {
                process.stdin.setRawMode(false);
                process.stdin.pause();
                reject(new Error('Cancelled by user.'));
                return;
            }

            if (key === '\r' || key === '\n') {
                process.stdin.removeListener('data', onData);
                process.stdin.setRawMode(false);
                process.stdout.write('\n');
                resolve(password);
                return;
            }

            if (key === '\u007f' || key === '\b') {
                password = password.slice(0, -1);
                return;
            }

            if (key >= ' ' && key <= '~') {
                password += key;
            }
        };

        process.stdin.setRawMode(true);
        process.stdin.resume();
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', onData);
    });
}

async function main() {
    try {
        const existingUsers = db
            .prepare('SELECT COUNT(*) AS count FROM users')
            .get().count;

        if (existingUsers > 0) {
            throw new Error(
                'The users table is not empty. No accounts were created.'
            );
        }

        const accounts = [];

        for (const user of users) {
            const password = await askHidden(
                `Enter password for ${user.username}: `
            );

            if (!password) {
                throw new Error('Passwords cannot be empty.');
            }

            accounts.push({
                ...user,
                password_hash: await bcrypt.hash(password, 12)
            });
        }

        const insertUser = db.prepare(`
            INSERT INTO users (username, password_hash, role)
            VALUES (@username, @password_hash, @role)
        `);

        const createAllUsers = db.transaction((accountList) => {
            for (const account of accountList) {
                insertUser.run(account);
            }
        });

        createAllUsers(accounts);

        console.log('\nAll six accounts were created successfully.');
    } catch (error) {
        console.error('\nAccount creation failed:', error.message);
        process.exitCode = 1;
    } finally {
        db.close();
        process.stdin.pause();
    }
}

main();
