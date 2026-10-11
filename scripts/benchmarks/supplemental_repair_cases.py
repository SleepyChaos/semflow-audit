"""Derived pure-module repair cases; hidden assertions never enter model source roots."""

from textwrap import dedent


def case(name, language, cwe, contract, original, reference, normal, security):
    extension = "py" if language == "python" else "js"
    prefix = (
        "from module import *\n"
        if language == "python"
        else "const assert=require('node:assert/strict');const m=require('./module.js');\n"
    )
    return {
        "id": name,
        "language": language,
        "cwe": cwe,
        "file": f"module.{extension}",
        "contract": contract,
        "original": dedent(original).lstrip(),
        "reference": dedent(reference).lstrip(),
        "normal": prefix + dedent(normal).lstrip(),
        "security": prefix + dedent(security).lstrip(),
    }


def cases():
    rows = []
    rows.append(
        case(
            "py-html",
            "python",
            "CWE-79",
            "render_name(value) returns an HTML text fragment for a user display name. Preserve ordinary text and Unicode; encode HTML metacharacters, do not remove the name.",
            "def render_name(value):\n    return '<span>' + value + '</span>'\n",
            "from html import escape\ndef render_name(value):\n    return '<span>' + escape(value, quote=True) + '</span>'\n",
            "assert render_name('Ada') == '<span>Ada</span>'\nassert '中文' in render_name('中文')\n",
            "out=render_name('<img src=x onerror=1>')\nassert '<img' not in out and '&lt;' in out\nassert '&amp;' in render_name('A&B')\n",
        )
    )
    rows.append(
        case(
            "py-sql",
            "python",
            "CWE-89",
            "prepare_name(name) returns (SQL string, list of parameters) for sqlite SELECT name FROM users WHERE name equals the untrusted name. Preserve exact-name matching and tuple API; use sqlite parameters, never delete the operation.",
            'def prepare_name(name):\n    return "SELECT name FROM users WHERE name = \'" + name + "\'", []\n',
            "def prepare_name(name):\n    return 'SELECT name FROM users WHERE name = ?', [name]\n",
            "import sqlite3\nc=sqlite3.connect(':memory:')\nc.execute('CREATE TABLE users(name TEXT)')\nc.executemany('INSERT INTO users VALUES (?)',[('Ada',),('Sam',)])\nassert c.execute(*prepare_name('Ada')).fetchall()==[('Ada',)]\nassert c.execute(*prepare_name('Unknown')).fetchall()==[]\n",
            "import sqlite3\nc=sqlite3.connect(':memory:')\nc.execute('CREATE TABLE users(name TEXT)')\nc.executemany('INSERT INTO users VALUES (?)',[('Ada',),('Sam',)])\nassert c.execute(*prepare_name(\"' OR 1=1 --\")).fetchall()==[]\nassert c.execute(*prepare_name(\"O'Reilly\")).fetchall()==[]\n",
        )
    )
    rows.append(
        case(
            "py-owner",
            "python",
            "CWE-639",
            "read_record(records, actor, key) returns records[key]['value'] only when its owner equals actor. Preserve legitimate owner access; a different owner's key raises PermissionError; missing keys retain KeyError.",
            "def read_record(records, actor, key):\n    return records[key]['value']\n",
            "def read_record(records, actor, key):\n    row=records[key]\n    if row['owner'] != actor:\n        raise PermissionError('owner mismatch')\n    return row['value']\n",
            "r={'a':{'owner':'alice','value':7},'b':{'owner':'bob','value':9}}\nassert read_record(r,'alice','a')==7\nassert read_record(r,'bob','b')==9\n",
            "r={'a':{'owner':'alice','value':7}}\ntry:\n    read_record(r,'bob','a')\nexcept PermissionError:\n    pass\nelse:\n    raise AssertionError('foreign owner accepted')\n",
        )
    )
    rows.append(
        case(
            "py-header",
            "python",
            "CWE-113",
            "make_header(value) returns 'X-Label: '+value for ordinary label text including spaces and Unicode. Reject CR or LF anywhere with ValueError; do not strip or silently truncate input.",
            "def make_header(value):\n    return 'X-Label: ' + value\n",
            "def make_header(value):\n    if '\\r' in value or '\\n' in value:\n        raise ValueError('line break')\n    return 'X-Label: ' + value\n",
            "assert make_header('Ada Lovelace')=='X-Label: Ada Lovelace'\nassert make_header('中文')=='X-Label: 中文'\nassert make_header('')=='X-Label: '\n",
            "for value in ['ok\\r\\nInjected: yes','bad\\n','bad\\r']:\n    try:\n        make_header(value)\n    except ValueError:\n        pass\n    else:\n        raise AssertionError('header delimiter accepted')\n",
        )
    )
    rows.append(
        case(
            "py-redirect",
            "python",
            "CWE-601",
            "redirect_path(value) returns the unchanged destination if it is a site-relative absolute path with exactly one initial '/', no backslash, CR or LF. Preserve query strings and fragments. Invalid values raise ValueError; no external or protocol-relative targets.",
            "def redirect_path(value):\n    if value.startswith('/'):\n        return value\n    raise ValueError('relative path required')\n",
            "def redirect_path(value):\n    if not value.startswith('/') or value.startswith('//') or any(x in value for x in ['\\\\','\\r','\\n']):\n        raise ValueError('invalid target')\n    return value\n",
            "for value in ['/','/account','/page?q=1#x']:\n    assert redirect_path(value)==value\n",
            "for value in ['//evil.invalid/x','/\\\\evil.invalid','/ok\\r\\nX: bad']:\n    try:\n        redirect_path(value)\n    except ValueError:\n        pass\n    else:\n        raise AssertionError('external target accepted')\n",
        )
    )
    rows.append(
        case(
            "js-html",
            "javascript",
            "CWE-79",
            "renderName(value) returns an HTML text fragment, preserving ordinary and Unicode display names; encode &, <, >, quotes rather than deleting input.",
            "exports.renderName=value=>'<span>'+value+'</span>';\n",
            "exports.renderName=value=>'<span>'+value.replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]))+'</span>';\n",
            "assert.equal(m.renderName('Ada'),'<span>Ada</span>');assert.ok(m.renderName('中文').includes('中文'));\n",
            "assert.ok(!m.renderName('<img src=x onerror=1>').includes('<img'));assert.ok(m.renderName('A&B').includes('&amp;'));\n",
        )
    )
    rows.append(
        case(
            "js-owner",
            "javascript",
            "CWE-639",
            "readRecord(records, actor, key) returns records[key].value only to its owner. Normal owner access preserves values; foreign access throws Error. Keep export and argument order.",
            "exports.readRecord=(records,actor,key)=>records[key].value;\n",
            "exports.readRecord=(records,actor,key)=>{const r=records[key];if(r.owner!==actor)throw new Error('owner mismatch');return r.value;};\n",
            "const r={a:{owner:'alice',value:7},b:{owner:'bob',value:9}};assert.equal(m.readRecord(r,'alice','a'),7);assert.equal(m.readRecord(r,'bob','b'),9);\n",
            "assert.throws(()=>m.readRecord({a:{owner:'alice',value:7}},'bob','a'));\n",
        )
    )
    rows.append(
        case(
            "js-header",
            "javascript",
            "CWE-113",
            "makeHeader(value) returns 'X-Label: '+value for normal labels, spaces, empty text and Unicode. Any CR or LF raises Error. Do not silently strip or truncate.",
            "exports.makeHeader=value=>'X-Label: '+value;\n",
            "exports.makeHeader=value=>{if(/[\\r\\n]/.test(value))throw new Error('line break');return 'X-Label: '+value;};\n",
            "for(const v of ['Ada Lovelace','中文',''])assert.equal(m.makeHeader(v),'X-Label: '+v);\n",
            "for(const v of ['ok\\r\\nInjected: yes','bad\\n','bad\\r'])assert.throws(()=>m.makeHeader(v));\n",
        )
    )
    rows.append(
        case(
            "js-redirect",
            "javascript",
            "CWE-601",
            "redirectPath(value) preserves only site-relative absolute paths starting with exactly one '/', without backslash/CR/LF. Preserve normal queries/fragments; reject all other values with Error.",
            "exports.redirectPath=value=>{if(value.startsWith('/'))return value;throw new Error('relative path required');};\n",
            "exports.redirectPath=value=>{if(!value.startsWith('/')||value.startsWith('//')||/[\\\\\\r\\n]/.test(value))throw new Error('invalid target');return value;};\n",
            "for(const v of ['/','/account','/page?q=1#x'])assert.equal(m.redirectPath(v),v);\n",
            "for(const v of ['//evil.invalid/x','/\\\\evil.invalid','/ok\\r\\nX: bad'])assert.throws(()=>m.redirectPath(v));\n",
        )
    )
    rows.append(
        case(
            "js-prototype",
            "javascript",
            "CWE-1321",
            "setPath(target, path, value) updates dot-separated keys on the supplied object, preserving unrelated fields; creates missing ordinary nested objects and returns target. Reject any path component __proto__, constructor or prototype with Error before changing any object. This is a pure module; no HTTP service.",
            "exports.setPath=(target,path,value)=>{const keys=path.split('.');let node=target;for(const k of keys.slice(0,-1)){node=node[k]||(node[k]={});}node[keys.at(-1)]=value;return target;};\n",
            "exports.setPath=(target,path,value)=>{const keys=path.split('.');if(keys.some(k=>['__proto__','constructor','prototype'].includes(k)))throw new Error('unsafe key');let node=target;for(const k of keys.slice(0,-1)){node=node[k]||(node[k]={});}node[keys.at(-1)]=value;return target;};\n",
            "const obj={keep:3};assert.equal(m.setPath(obj,'user.name','Ada'),obj);assert.equal(obj.user.name,'Ada');assert.equal(obj.keep,3);\n",
            "for(const path of ['__proto__.polluted','constructor.prototype.polluted','safe.__proto__.polluted']){assert.throws(()=>m.setPath({},path,true));}assert.equal({}.polluted,undefined);\n",
        )
    )
    return rows
