const multer = require('multer');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const uploadDirectory = path.join(__dirname, '..', 'uploads');
const MIN_FREE_SPACE = 10 * 1024 * 1024 * 1024;

fs.mkdirSync(uploadDirectory, { recursive: true });

const storage = multer.diskStorage({
    destination: (req, file, callback) => {
        callback(null, uploadDirectory);
    },

    filename: (req, file, callback) => {
        const randomName = crypto.randomBytes(32).toString('hex');
        callback(null, `${randomName}.upload`);
    }
});

const upload = multer({
    storage,

    limits: {
        fileSize: 200 * 1024 * 1024,
        files: 1,
        fields: 5,
        parts: 6,
        fieldSize: 10 * 1024
    }
});

async function checkDiskSpace(req, res, next) {
    try {
        const stats = await fs.promises.statfs(uploadDirectory);
        const freeSpace = stats.bavail * stats.bsize;

        if (freeSpace < MIN_FREE_SPACE) {
            return res.status(507).render('upload', {
                user: req.session.user,
                error: 'Δεν υπάρχει αρκετός ελεύθερος χώρος στον δίσκο. Απαιτούνται τουλάχιστον 10 GB.'
            });
        }

        next();
    } catch (error) {
        next(error);
    }
}

async function validateVideoFile(req, res, next) {
    if (!req.file) {
        return res.status(400).render('upload', {
            user: req.session.user,
            error: 'Πρέπει να επιλέξεις ένα αρχείο βίντεο.'
        });
    }

    try {
        const { fileTypeFromFile } = await import('file-type');
        const detectedType = await fileTypeFromFile(req.file.path);

        const allowedTypes = {
            mp4: 'video/mp4',
            mov: 'video/quicktime',
            webm: 'video/webm',
            mkv: 'video/x-matroska',
            avi: 'video/x-msvideo'
        };

        if (
            !detectedType ||
            allowedTypes[detectedType.ext] !== detectedType.mime
        ) {
            await fs.promises.unlink(req.file.path).catch(() => {});

            return res.status(400).render('upload', {
                user: req.session.user,
                error: 'Το αρχείο δεν αναγνωρίζεται ως υποστηριζόμενο βίντεο. Δοκίμασε MP4, MOV, WebM, MKV ή AVI.'
            });
        }

        req.detectedVideoType = detectedType;
        next();
    } catch (error) {
        await fs.promises.unlink(req.file.path).catch(() => {});
        next(error);
    }
}



async function deleteTemporaryUpload(req) {
    if (req.file && req.file.path) {
        try {
            await fs.promises.unlink(req.file.path);
        } catch (error) {
            if (error.code !== 'ENOENT') {
                throw error;
            }
        }
    }
}


module.exports = {
    upload,
    checkDiskSpace,
    validateVideoFile,
    deleteTemporaryUpload
};
