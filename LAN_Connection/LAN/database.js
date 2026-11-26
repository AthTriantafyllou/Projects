const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const dataDirectory = path.join(__dirname, 'data');

fs.mkdirSync(dataDirectory, { recursive: true });

const databasePath = path.join(dataDirectory, 'project.db');

const db = new Database(databasePath);

db.pragma('foreign_keys = ON');
db.pragma('busy_timeout = 5000');

module.exports = db;
