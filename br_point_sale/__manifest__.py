# -*- coding: utf-8 -*-
# © 2016 Danimar Ribeiro, Trustcode
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    'name': 'Point of Sale Brazil',
    'summary': """Module to adapt Odoo Point of Sale to Brazil""",
    'description': 'Point of Sale Brazil',
    'version': '11.0.1.0.0',
    'category': 'pos',
    'author': 'Raphael Rodrigues <raphael0608@gmail.com>',
    'license': 'AGPL-3',
    'website': 'http://www.trustcode.com.br',
    'contributors': [
        'Raphael Rodrigues <raphael0608@gmail.com>'
    ],
    'depends': [
        'point_of_sale', 'br_nfe',
        'base_report_to_printer',
    ],
    'external_dependencies': {
        'python': [
            'pytrustnfe',
        ],
    },
    'data': [
        'views/br_account_journal.xml',
        'views/pos_order.xml',
        'views/br_pos_templates.xml',
        'views/br_pos_session.xml',
        'reports/danfce_report.xml',
        'reports/close_session.xml',
        'security/ir.model.access.csv',
    ],

    'qweb': [
        'static/src/xml/pos.xml',
    ],

    'application': True,
    'installable': True,

}
