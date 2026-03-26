{
    'name': 'Installment Tracker',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Installment tracking widget in invoice form',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ms_installment_tracker/static/src/js/installment_tracker_widget.js',
            'ms_installment_tracker/static/src/xml/installment_tracker_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
