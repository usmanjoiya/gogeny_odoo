/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const STORAGE_KEY = "recent_products";
const MAX_HISTORY = 12;
const MAX_DISPLAY = 4;

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[c]));
}

function getCurrentProductId() {
    const input = document.querySelector(
        'input[name="product_template_id"], input.product_template_id'
    );
    if (input && input.value) {
        const id = parseInt(input.value, 10);
        if (!isNaN(id)) return id;
    }
    const jsonLd = document.querySelector('script[type="application/ld+json"]');
    if (jsonLd) {
        try {
            const data = JSON.parse(jsonLd.textContent);
            if (data && data.productID) return parseInt(data.productID, 10);
        } catch (e) {}
    }
    return null;
}

function readHistory() {
    try {
        const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        return raw.map(Number).filter((n) => n && !isNaN(n));
    } catch (e) {
        return [];
    }
}

function writeHistory(ids) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

async function initRecentProducts() {
    const section = document.getElementById("recent_products_section");
    if (!section) return;
    const container = section.querySelector("#recent_products_container");
    if (!container) return;

    const currentId = getCurrentProductId();

    let viewed = readHistory();
    if (currentId) {
        viewed = viewed.filter((p) => p !== currentId);
        viewed.unshift(currentId);
        viewed = viewed.slice(0, MAX_HISTORY);
        writeHistory(viewed);
    }

    const displayIds = viewed.filter((p) => p !== currentId).slice(0, MAX_DISPLAY);
    if (!displayIds.length) return;

    let data;
    try {
        data = await rpc("/recent/products", { product_ids: displayIds });
    } catch (e) {
        return;
    }
    if (!data || !data.length) return;

    container.innerHTML = "";
    data.forEach((p) => {
        const col = document.createElement("div");
        col.className = "col-6 col-md-3 mb-3";
        col.innerHTML = `
            <div class="card h-100 shadow-sm">
                <a href="${escapeHtml(p.url)}">
                    <img src="${escapeHtml(p.image)}" class="card-img-top" alt="${escapeHtml(p.name)}"/>
                </a>
                <div class="card-body text-center">
                    <h6 class="card-title">
                        <a href="${escapeHtml(p.url)}" class="text-reset text-decoration-none">${escapeHtml(p.name)}</a>
                    </h6>
                    <p class="card-text fw-bold mb-0">${escapeHtml(p.price)} ${escapeHtml(p.currency)}</p>
                </div>
            </div>
        `;
        container.appendChild(col);
    });
    section.classList.remove("d-none");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRecentProducts);
} else {
    initRecentProducts();
}
