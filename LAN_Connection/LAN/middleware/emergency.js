const activeUploads = new Set();

let wipeInProgress = false;

function isWipeInProgress() {
    return wipeInProgress;
}

function beginWipe() {
    if (wipeInProgress) {
        return false;
    }

    wipeInProgress = true;
    return true;
}

function endWipe() {
    wipeInProgress = false;
}

function registerUpload(upload) {
    activeUploads.add(upload);

    return () => {
        activeUploads.delete(upload);
    };
}


async function cancelActiveUploads() {
    const uploads = [...activeUploads];

    for (const upload of uploads) {
        upload.cancel();
    }

    const timeout = new Promise((_, reject) => {
        setTimeout(() => {
            reject(new Error(
                'Οι ενεργές μεταφορτώσεις δεν σταμάτησαν εγκαίρως.'
            ));
        }, 5000);
    });

    await Promise.race([
        Promise.all(uploads.map(upload => upload.done)),
        timeout
    ]);
}




module.exports = {
    isWipeInProgress,
    beginWipe,
    endWipe,
    registerUpload,
    cancelActiveUploads
};
