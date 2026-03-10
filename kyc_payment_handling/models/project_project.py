from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import re

class ProjectProject(models.Model):
    _inherit = 'project.project'

    phone = fields.Char(string="Phone")
    product_id = fields.Many2one('product.template', string="Product")
    emergency_phone = fields.Char(string="Emergency Phone")
    email = fields.Char(string="Email")
    place_of_work = fields.Char(string="Place of Work")
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")
    city = fields.Char(string="City")
    state_id = fields.Many2one('res.country.state', string="State")
    zip_code = fields.Char(string="Zip")
    bank_state_password = fields.Char(string="Bank State Password")
    country_id = fields.Many2one('res.country', string="Country")
    uae_id_number = fields.Char(string="UAE ID Number")
    payment_term_id = fields.Many2one('account.payment.term', string="Payment Term")
    id_photo_front = fields.Binary(string="ID Photo Front", attachment=True)
    id_photo_front_filename = fields.Char(string="ID Photo Front Filename")
    id_photo_back = fields.Binary(string="ID Photo Back", attachment=True)
    id_photo_back_filename = fields.Char(string="ID Photo Back Filename")
    bank_statement = fields.Binary(string="3M Bank Statement", attachment=True)
    bank_statement_filename = fields.Char(string="Bank Statement Filename")
    salary_certificate = fields.Binary(string="Salary Certificate", attachment=True)
    salary_certificate_filename = fields.Char(string="Salary Certificate Filename")
    cheque_photo = fields.Binary(string="Bank Check Image", attachment=True)
    cheque_photo_filename = fields.Char(string="Bank Check Photo Filename")

    customer_signature = fields.Binary(string="Customer Signature", attachment=True)
    customer_signature_filename = fields.Char(string="Customer Signature Filename")

    last_update_status = fields.Selection(selection_add=[('no_task', 'No Task')], ondelete={'no_task': 'set default'})

    state = fields.Selection(
        [('recieved', 'Recieved'), ('in_review', 'In-Review'), ('approved', 'Approved'),  ('contract_sent', 'Contract Sent'), ('reject', 'Rejected')],
        string="Status", default="recieved")
    
    invoice_ref_id = fields.Many2one('account.move', string="Invoice Ref", store=True)
    sale_order_id = fields.Many2one('sale.order', string="Sale Order Ref", store=True)

    invoice_date = fields.Date(string="Invoice Date")

    partner_invoice_count = fields.Integer(
        string="Previous Invoices",
        compute='_compute_partner_invoice_count',
    )

    @api.depends('partner_id')
    def _compute_partner_invoice_count(self):
        for rec in self:
            if rec.partner_id:
                rec.partner_invoice_count = self.env['account.move'].search_count([
                    ('partner_id', '=', rec.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                ])
            else:
                rec.partner_invoice_count = 0

    def _apply_installment_product_invoice(self, invoice):
        """Create and attach installment product line on invoice."""
        for rec in self:
            if not rec.payment_term_id or not rec.payment_term_id.installment_amount:
                return

            product_name = f"Installment - {rec.payment_term_id.name} ({rec.payment_term_id.id})"

            product_tmpl = self.env['product.template'].search([('name', '=', product_name)], limit=1)
            if not product_tmpl:
                product_tmpl = self.env['product.template'].create({
                    'name': product_name,
                    'list_price': rec.payment_term_id.installment_amount,
                    'type': 'service',
                    'taxes_id': [(5, 0, 0)],
                    'supplier_taxes_id': [(5, 0, 0)],
                    'installment_product': True,
                })
            else:
                # Update price if needed
                if product_tmpl.list_price != rec.payment_term_id.installment_amount:
                    product_tmpl.list_price = rec.payment_term_id.installment_amount
                # Clear taxes
                product_tmpl.taxes_id = [(5, 0, 0)]
                product_tmpl.supplier_taxes_id = [(5, 0, 0)]

            product = product_tmpl.product_variant_id

            # Add invoice line if main product matches payment term’s product_ids
            if rec.product_id and rec.product_id.id in rec.payment_term_id.product_ids.ids:
                self.env['account.move.line'].create({
                    'move_id': invoice.id,
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': product.list_price,
                    'name': product.name,
                    'tax_ids': [(5, 0, 0)],
                })

    def action_send_contract(self):
        self.ensure_one()

        if not self.partner_id:
            raise ValidationError("Please provide 'Customer' before sending contract.")
        
        if not self.product_id:
            raise ValidationError("Please provide 'Product' before sending contract.")
        
        if not self.company_id:
            raise ValidationError("Please provide 'Company' before sending contract.")

        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_payment_term_id': self.payment_term_id.id,
            'company_id': self.partner_id.company_id.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_id.product_variant_id.id,
                    'quantity': 1,
                    'price_unit': self.product_id.list_price,
                    'name': self.product_id.product_variant_id.name,
                })
            ],
        }

        invoice = self.env['account.move'].create(invoice_vals)

        self._apply_installment_product_invoice(invoice)

        invoice.action_post()

        self.invoice_date = invoice.invoice_date
        self.invoice_ref_id = invoice.id


        template = self.env.ref("kyc_payment_handling.email_template_customer_contract", raise_if_not_found=False)
        report = self.env.ref("kyc_payment_handling.action_print_contract", raise_if_not_found=False)
        if template and report:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'kyc_payment_handling.action_print_contract', self.id
            )

            pdf_name = f"Customer_Contract_{self.name or 'Document'}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'project.project',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            template.send_mail(
                self.id,
                force_send=True,
                email_values={'attachment_ids': [attachment.id]}
            )

            self.state = "contract_sent"
            stage = self.env.ref(
                "kyc_payment_handling.project_project_stage_contract_sent",
                raise_if_not_found=False
            )
            if stage:
                self.stage_id = stage.id

        self.invoice_ref_id = None
        invoice.button_draft()
        invoice.button_cancel()
        invoice.sudo().unlink()

    def action_resend_contract(self):
        self.ensure_one()
        template = self.env.ref("kyc_payment_handling.email_template_customer_contract", raise_if_not_found=False)
        if not template:
            raise ValidationError("Email template not found.")
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'project.project'),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf'),
        ], order='id desc', limit=1)
        if not attachment:
            raise ValidationError("No contract PDF found. Please send the contract first.")
        template.send_mail(
            self.id,
            force_send=True,
            email_values={'attachment_ids': [attachment.id]}
        )

    @api.constrains('bank_statement', 'salary_certificate', 'id_photo_front', 'id_photo_back')
    def _check_file_size(self):
        max_size = 20 * 1024 * 1024
        for record in self:
            if record.id_photo_front and len(record.id_photo_front) > max_size:
                raise ValidationError("ID Photo Front file size cannot exceed 20 MB.")
            if record.id_photo_back and len(record.id_photo_back) > max_size:
                raise ValidationError("ID Photo Back file size cannot exceed 20 MB.")
            if record.bank_statement and len(record.bank_statement) > max_size:
                raise ValidationError("Bank Statement file size cannot exceed 20 MB.")
            if record.salary_certificate and len(record.salary_certificate) > max_size:
                raise ValidationError("Salary Certificate file size cannot exceed 20 MB.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("stage_id"):
                stage = self.env.ref(
                    "kyc_payment_handling.project_project_stage_received",
                    raise_if_not_found=False
                )
                if stage:
                    vals["stage_id"] = stage.id
        return super().create(vals_list)

    def action_state_in_review(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise ValidationError("Customer is missing!")
        user = self.env.user
        template = self.env.ref("kyc_payment_handling.email_template_project_review", raise_if_not_found=False)
        if template:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={'email_to': partner.email,'email_from': user.email or ''},
            )
        self.state = "in_review"
        stage = self.env.ref(
            "kyc_payment_handling.project_project_stage_in_review",
            raise_if_not_found=False
        )
        if stage:
            self.stage_id = stage.id

    def action_state_approved(self):
        self.ensure_one()
        self.state = "approved"
        stage = self.env.ref(
            "kyc_payment_handling.project_project_stage_approved",
            raise_if_not_found=False
        )
        if stage:
            self.stage_id = stage.id

    def action_state_reject(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise ValidationError("Customer is missing!")
        user = self.env.user
        template = self.env.ref("kyc_payment_handling.email_template_project_reject", raise_if_not_found=False)
        if template:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={'email_to': partner.email,'email_from': user.email or ''},
            )
        self.state = "reject"
        stage = self.env.ref(
            "kyc_payment_handling.project_project_stage_rejected",
            raise_if_not_found=False
        )
        print("--------->>>>>Stage", stage)
        if stage:
            self.stage_id = stage.id

    @api.onchange('uae_id_number')
    def onchange_uae_id_number(self):
        for rec in self:
            if rec.partner_id and not rec.partner_id.customer_reference:
                rec.partner_id.customer_reference = rec.uae_id_number

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for rec in self:
            if rec.company_id and rec.partner_id:
                partner = rec.partner_id
                
                user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
                user.sudo().write({
                    'company_id': rec.company_id.id,
                    'company_ids': [(6, 0, [rec.company_id.id])]
                })
                
                rec.partner_id.company_id = rec.company_id.id

    @api.depends('last_update_status')
    def _compute_last_update_color(self):
        for project in self:
            if project.last_update_status == 'no_task':
                project.last_update_color = 0
            else:
                super(ProjectProject, project)._compute_last_update_color()

    def write(self, vals):
        for rec in self:
            if rec.uae_id_number:
                partner = self.env['res.partner'].search([('customer_reference', '=', rec.uae_id_number)], limit=1)
                if partner:
                    vals['partner_id'] = partner.id
        return super().write(vals)

    def unlink(self):
        self.env['res.partner.project.line'].sudo().search([
            ('project_id', 'in', self.ids)
        ]).unlink()
        return super().unlink()


class ProjectUpdate(models.Model):
    _inherit = 'project.update'

    status = fields.Selection(selection_add=[('no_task', 'No Task')], ondelete={'no_task': 'cascade'})

    @api.depends('status')
    def _compute_color(self):
        for update in self:
            if update.status == 'no_task':
                update.color = 0
            else:
                super(ProjectUpdate, update)._compute_color()

