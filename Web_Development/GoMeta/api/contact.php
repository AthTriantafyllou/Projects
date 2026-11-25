<?php
declare(strict_types=1);

// Receives the contact form and emails it to the studio.
// The recipient and domain come from src/data/site.json (filled in by build.mjs).

const TO_EMAIL = 'hello@gometa.gr';
const FROM_EMAIL = 'no-reply@thanfyllou.eu';
const SUBJECT_PREFIX = '[Website]';

function respond(bool $ok, string $message, int $status = 200): void
{
    $wantsJson = ($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') === 'fetch';

    if ($wantsJson) {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok' => $ok, 'message' => $message]);
    } else {
        header('Location: /gometa3/contact/?' . ($ok ? 'sent=1' : 'error=1'));
    }
    exit;
}

function clean(string $key, int $maxLength): string
{
    $value = trim((string) ($_POST[$key] ?? ''));
    $value = preg_replace('/[\r\n]+/', ' ', $value) ?? '';
    return mb_substr($value, 0, $maxLength);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    exit;
}

// Spam trap: real visitors never fill this hidden field. Pretend it worked.
if (trim((string) ($_POST['website'] ?? '')) !== '') {
    respond(true, 'Thank you! Your message is on its way.');
}

$name = clean('name', 100);
$email = clean('email', 160);
$topic = clean('topic', 40);
$message = trim((string) ($_POST['message'] ?? ''));
$message = mb_substr($message, 0, 5000);

if ($name === '' || !filter_var($email, FILTER_VALIDATE_EMAIL) || mb_strlen($message) < 10) {
    respond(false, 'Please fill in your name, a valid email and a short message.', 422);
}

$subject = sprintf('%s %s: %s', SUBJECT_PREFIX, $topic !== '' ? $topic : 'Enquiry', $name);
$body = "Name: $name\nEmail: $email\nTopic: $topic\n\n$message\n";

$headers = [
    'From: ' . FROM_EMAIL,
    'Reply-To: ' . $email,
    'Content-Type: text/plain; charset=UTF-8',
    'MIME-Version: 1.0',
];

$sent = mail(TO_EMAIL, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, implode("\r\n", $headers));

if (!$sent) {
    respond(false, 'We could not send your message. Please email us at ' . TO_EMAIL . '.', 500);
}

respond(true, 'Thank you! Your message is on its way. We reply within a working day.');
