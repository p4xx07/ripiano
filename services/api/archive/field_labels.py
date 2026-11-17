"""Readable names for request fields, used in validation messages instead of raw keys like `filter_text`.

The Italian versions live in `messages_it.VALUES`, which translates these names when they fill a message template.
"""

LABELS = {
    "name": "Name",
    "host": "Server",
    "username": "User name",
    "folder": "Folder",
    "move_to": "Move-to folder",
    "filter_from": "Sender filter",
    "filter_subject": "Subject filter",
    "filter_body": "Message text filter",
    "filter_attachment": "Attachment name filter",
    "filter_filename": "File name filter",
    "filter_text": "Text filter",
    "action_note": "Action note",
    "add_note": "Note",
    "email_to": "Email recipients",
    "webhook_url": "Webhook address",
    "endpoint": "Address",
    "region": "Region",
    "bucket": "Bucket",
    "path": "Folder",
    "include_patterns": "Include patterns",
    "exclude_patterns": "Skip patterns",
    "processed_path": "Processed folder",
}


def label(key):
    return LABELS.get(key, key.replace("_", " ").capitalize())
