"""Frozen development pairs. Labels never enter detector inputs."""


def cases(complete_entrypoints=False):
    result = {}
    for safe in (False, True):
        suffix = "safe" if safe else "vulnerable"
        result["ownership_" + suffix] = {
            "vulnerable": not safe,
            "cwes": ["CWE-639", "CWE-862", "CWE-863", "CWE-285", "CWE-284"],
            "root": "An authenticated user may read only an order they own.",
            "files": {
                "README.md": "OrderDesk is a custom RPC module. view_order is an externally reachable handler. The host authenticates user; order_id is chosen by that user. There are no host ownership checks: this module must enforce them. Orders contain owner_id and payload. Only the owner may read an order.\n",
                "app.py": "from guards import assert_owner\n\ndef view_order(user, order_id, orders):\n    order = orders[order_id]\n"
                + ("    assert_owner(user, order)\n" if safe else "")
                + "    return order.payload\n\nHANDLERS = {'view_order': view_order}\n",
                "guards.py": "def assert_owner(user, order):\n    if order.owner_id != user.id:\n        raise PermissionError('not owner')\n",
            },
        }
        result["tenant_" + suffix] = {
            "vulnerable": not safe,
            "cwes": ["CWE-639", "CWE-862", "CWE-863", "CWE-285", "CWE-284"],
            "root": "A tenant admin may read only their own tenant's workspace.",
            "files": {
                "README.md": "WorkspaceDesk exposes workspace_info directly through a custom RPC dispatcher. The host authenticates user. workspace_id is externally supplied; workspaces is a server-side mapping. A user with role tenant_admin is authorized only within user.tenant_id. No other layer checks the target workspace tenant.\n",
                "app.py": "def workspace_info(user, workspace_id, workspaces):\n    if user.role != 'tenant_admin':\n        raise PermissionError('admin required')\n    workspace = workspaces[workspace_id]\n"
                + (
                    "    if workspace.tenant_id != user.tenant_id:\n        raise PermissionError('wrong tenant')\n"
                    if safe
                    else ""
                )
                + "    return workspace.details\n\nHANDLERS = {'workspace_info': workspace_info}\n",
            },
        }
        result["state_" + suffix] = {
            "vulnerable": not safe,
            "cwes": ["CWE-841", "CWE-840", "CWE-863", "CWE-862", "CWE-20"],
            "root": "A payment record must be approved before it can be released.",
            "files": {
                "README.md": "PaymentDesk exposes release_payment directly to authenticated operators. The caller selects a payment record but cannot modify server-side record fields. Records have state draft, approved or paid and a trusted amount. Operators may release ONLY approved records. No host/dispatcher performs the state check. Returning released_amount requests payment from the downstream accounting system.\n",
                "app.py": "def release_payment(operator, record):\n"
                + (
                    "    if record['state'] != 'approved':\n        raise ValueError('approval required')\n"
                    if safe
                    else ""
                )
                + "    record['state'] = 'paid'\n    return {'released_amount': record['amount']}\n\nHANDLERS = {'release_payment': release_payment}\n",
            },
        }
    if complete_entrypoints:
        identities = "from types import SimpleNamespace\nfrom app import HANDLERS\n\nSESSIONS = {'alice_session': SimpleNamespace(id=1, tenant_id=1, role='tenant_admin'), 'bob_session': SimpleNamespace(id=2, tenant_id=2, role='tenant_admin')}\n\n"
        for name, case in result.items():
            if name.startswith("ownership"):
                host = "ORDERS = {1: SimpleNamespace(owner_id=1, payload='alice-private'), 2: SimpleNamespace(owner_id=2, payload='bob-private')}\n\ndef dispatch(session_token, arguments):\n    authenticated_user = SESSIONS[session_token]\n    return HANDLERS['view_order'](authenticated_user, int(arguments['order_id']), ORDERS)\n"
            elif name.startswith("tenant"):
                host = "WORKSPACES = {1: SimpleNamespace(tenant_id=1, details='tenant-one-private'), 2: SimpleNamespace(tenant_id=2, details='tenant-two-private')}\n\ndef dispatch(session_token, arguments):\n    authenticated_user = SESSIONS[session_token]\n    return HANDLERS['workspace_info'](authenticated_user, int(arguments['workspace_id']), WORKSPACES)\n"
            else:
                host = "RECORDS = {1: {'state': 'draft', 'amount': 100}, 2: {'state': 'approved', 'amount': 200}}\n\ndef dispatch(session_token, arguments):\n    authenticated_user = SESSIONS[session_token]\n    record = RECORDS[int(arguments['record_id'])]\n    return HANDLERS['release_payment'](authenticated_user, record)\n"
            case["files"]["host.py"] = identities + host
            case["files"]["README.md"] += (
                "host.py contains the complete dispatcher and development fixture data; the session names are test substitutes, not production credentials. dispatch's arguments are caller-controlled, while SESSIONS and resource maps are server-held. There is no additional dispatcher implementation in this project.\n"
            )
    return result
