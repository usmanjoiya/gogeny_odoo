{
    'name': 'Installment Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Standalone installment tracking dashboard from invoice data',
    'depends': ['kyc_payment_handling', 'account'],
    'data': [
        'views/installment_line_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'installment_dashboard/static/src/js/installment_dashboard.js',
            'installment_dashboard/static/src/xml/installment_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
