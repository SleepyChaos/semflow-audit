"""New derived data-flow/control-flow probes for six existing rule families."""

from textwrap import dedent


def fixture(language, body, positive):
    extension = "py" if language == "python" else "js"
    text = dedent(body).lstrip()
    name = "probe." + extension
    expected = [
        {"file": name, "line": i}
        for i, line in enumerate(text.splitlines(), 1)
        if "target" in line and positive
    ]
    return {"files": {name: text}, "expected": expected}


def datasets():
    probes = {
        "python-eval": (
            """
            from flask import Flask, request
            app = Flask(__name__)
            def calculate(expression):
                return eval(expression) # target
            @app.post('/compute')
            def compute():
                payload = request.form['expression']
                return str(calculate(payload))
            @app.get('/alternate')
            def alternate():
                incoming = request.args.get('expression', '')
                execute = eval
                return str(execute(incoming)) # target
            """,
            """
            from flask import Flask, request
            app = Flask(__name__)
            @app.get('/safe')
            def safe():
                text = request.args.get('expression', '')
                if text != '2 + 3':
                    return 'rejected'
                return str(eval('2 + 3'))
            @app.get('/shadow')
            def shadow():
                def eval(text):
                    return len(text)
                return str(eval(request.args['expression']))
            """,
        ),
        "python-sql": (
            """
            from flask import Flask, request
            import sqlite3
            app = Flask(__name__)
            def make_sql(value):
                return "SELECT name FROM users WHERE name='" + value + "'"
            @app.post('/lookup')
            def lookup():
                value = request.form['name']
                conn = sqlite3.connect(':memory:')
                statement = make_sql(value)
                return str(conn.execute(statement).fetchall()) # target
            @app.get('/lookup2')
            def alternate():
                conn = sqlite3.connect(':memory:')
                statement = "SELECT name FROM users WHERE name='{}'".format(request.args['name'])
                return str(conn.execute(statement).fetchall()) # target
            """,
            """
            from flask import Flask, request
            import sqlite3
            app = Flask(__name__)
            @app.post('/safe')
            def safe():
                conn = sqlite3.connect(':memory:')
                statement = 'SELECT name FROM users WHERE name=?'
                return str(conn.execute(statement, (request.form['name'],)).fetchall())
            @app.get('/constant')
            def constant():
                conn = sqlite3.connect(':memory:')
                return str(conn.execute("SELECT name FROM users WHERE name='Ada'").fetchall())
            """,
        ),
        "python-xss": (
            """
            from flask import Flask, request
            app = Flask(__name__)
            def fragment(value):
                return '<span>' + value + '</span>'
            @app.post('/preview')
            def preview():
                return fragment(request.form['name']) # target
            @app.get('/preview2')
            def alternate():
                values = request.args
                fragment = '<p>' + values['name'] + '</p>'
                return fragment # target
            """,
            """
            from flask import Flask, request
            from markupsafe import escape
            app = Flask(__name__)
            @app.post('/safe')
            def safe():
                value = escape(request.form['name'])
                return '<span>' + str(value) + '</span>'
            @app.get('/constant')
            def constant():
                ignored = request.args['name']
                return '<p>Ada</p>'
            """,
        ),
        "javascript-eval": (
            """
            const express = require('express');
            const app = express();
            function calculate(text) { return eval(text); } // target
            app.post('/compute', (req, res) => {
              res.json({value: calculate(req.body.expression)});
            });
            app.get('/alternate', (req, res) => {
              const incoming = req.query.expression;
              const execute = eval;
              res.json({value: execute(incoming)}); // target
            });
            """,
            """
            const express = require('express');
            const app = express();
            app.post('/safe', (req, res) => {
              const unused = req.body.expression;
              res.json({value: eval('2 + 3')});
            });
            app.get('/shadow', (req, res) => {
              function eval(text) { return text.length; }
              res.json({value: eval(req.query.expression)});
            });
            """,
        ),
        "javascript-sql": (
            """
            const express = require('express');
            const app = express();
            function makeSql(value) { return "SELECT name FROM users WHERE name='" + value + "'"; }
            app.post('/lookup', (req, res) => {
              const conn = require('mysql').createConnection({});
              const statement = makeSql(req.body.name);
              conn.query(statement); // target
            });
            app.get('/lookup2', (req, res) => {
              const conn = require('mysql').createConnection({});
              const name = req.query.name;
              conn.query(`SELECT name FROM users WHERE name='${name}'`); // target
            });
            """,
            """
            const express = require('express');
            const app = express();
            app.post('/safe', (req, res) => {
              const conn = require('mysql').createConnection({});
              const statement = 'SELECT name FROM users WHERE name=?';
              conn.query(statement, [req.body.name]);
            });
            app.get('/constant', (req, res) => {
              const conn = require('mysql').createConnection({});
              conn.query("SELECT name FROM users WHERE name='Ada'");
            });
            """,
        ),
        "javascript-xss": (
            """
            const express = require('express');
            const app = express();
            function fragment(name) { return '<span>' + name + '</span>'; }
            app.post('/preview', (req, res) => {
              res.send(fragment(req.body.name)); // target
            });
            app.get('/preview2', (req, res) => {
              const values = req.query;
              const body = '<p>' + values.name + '</p>';
              res.send(body); // target
            });
            """,
            """
            const express = require('express');
            const app = express();
            app.post('/safe', (req, res) => {
              res.json({name: req.body.name});
            });
            app.get('/constant', (req, res) => {
              const unused = req.query.name;
              res.send('<p>Ada</p>');
            });
            """,
        ),
    }
    return {
        family: {
            "language": family.split("-")[0],
            "fixtures": {
                "positive": fixture(family.split("-")[0], positive, True),
                "negative": fixture(family.split("-")[0], negative, False),
            },
            "provenance": "derived-unreviewed-flow-probes-not-natural-blind-gold",
        }
        for family, (positive, negative) in probes.items()
    }
