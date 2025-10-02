from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
    state = fields.Selection(
        [('recieved', 'Recieved'), ('in_review', 'In-Review'), ('approved', 'Approved'),  ('contract_sent', 'Contract Sent'), ('reject', 'Rejected')],
        string="Status", default="recieved")

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
