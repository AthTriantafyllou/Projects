const { z } = require('zod');
const fs = require('fs');

const submissionSchema = z.object({
    category: z.enum([
        'Λάθος κατηγορία',
        'Καμία κατηγορία - non detected',
        'Other'
    ]),

    description: z.string()
        .trim()
        .min(1, 'Η περιγραφή είναι υποχρεωτική.')
        .max(2000, 'Η περιγραφή δεν μπορεί να ξεπερνά τους 2.000 χαρακτήρες.'),

    event_time: z.union([
        z.literal(''),
        z.iso.datetime({ local: true })
    ]).optional()
});

async function validateSubmission(req, res, next) {
    const result = submissionSchema.safeParse({
        category: req.body.category,
        description: req.body.description,
        event_time: req.body.event_time
    });

    if (!result.success) {
        if (req.file?.path) {
            await fs.promises.unlink(req.file.path).catch(() => {});
        }

        return res.status(400).render('upload', {
            user: req.session.user,
            error: result.error.issues[0].message
        });
    }

    req.validatedSubmission = {
        ...result.data,
        event_time: result.data.event_time || null
    };

    next();
}

module.exports = {
    validateSubmission
};
