"""Callback id parsers for My Postings handlers."""


def parse_repost_premium_callback_id(data):
    return int(data.split("_")[2])


def parse_delete_premium_callback_id(data):
    return int(data.split("_")[2])


def parse_do_delete_premium_callback_id(data):
    return int(data.split("_")[3])


def parse_baraholka_mypostings_callback_id(data):
    return int(data.split(":", 2)[2])
