odoo.define('kyc_payment_handling.project_application', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ProjectApplicationValidation = publicWidget.Widget.extend({
        selector: '#applicationForm',
        events: {
            'submit': '_onFormSubmit',
        },

        _onFormSubmit: function (ev) {
            const maxSize = 20 * 1024 * 1024; // 20 MB
            let valid = true;

            // Remove old validation message if exists
            this.$('.file-size-error').remove();

            let filesToCheck = [
                {name: "id_photo_front", label: "ID Photo Front"},
                {name: "id_photo_back", label: "ID Photo Back"},
                {name: "3m_bank_statement", label: "3M Bank Statement"},
                {name: "salary_certificate", label: "Salary Certificate"},
            ];

            for (let f of filesToCheck) {
                let fileInput = this.el.querySelector(`input[name="${f.name}"]`);
                if (fileInput && fileInput.files.length > 0) {
                    let file = fileInput.files[0];
                    if (file.size > maxSize) {
                        ev.preventDefault(); // stop form submit
                        valid = false;

                        // Add a bootstrap alert just above the file input
                        let errorMsg = document.createElement("div");
                        errorMsg.className = "alert alert-danger file-size-error mt-2";
                        errorMsg.innerText = `${f.label} cannot exceed 20 MB.`;
                        fileInput.closest(".form-control").parentNode.appendChild(errorMsg);

                        break; // stop checking after first error
                    }
                }
            }

            return valid;
        },
    });
});
