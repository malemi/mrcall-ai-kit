#!/usr/bin/env python3
"""Retired completion adapter: quiet compatibility for already-loaded hooks.

New installations never register this path. Existing native sessions can retain
an old command definition until reload, so its hook action must stay harmless.
No reviews, receipts, bindings or completion certifications remain here.
"""
import json
import sys


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    if action == 'hook':
        print('{}')
    elif action == 'status':
        print(json.dumps({'retired': True, 'completion_certification': False}))
    else:
        print('The runtime completion certificate is retired; no review, bind, exec or on action remains.', file=sys.stderr)
        raise SystemExit(2)
