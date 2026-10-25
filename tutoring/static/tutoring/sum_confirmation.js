(() => {
    const photoForm = document.getElementById("photo-form");
    const box = document.getElementById("confirmation-box");
    const form = document.getElementById("confirmation-form");
    const button = document.getElementById("confirm-button");
    const message = document.getElementById("confirmation-message");
    const reviewBox = document.getElementById("review-action-box");
    const reviewForm = document.getElementById("review-action-form");
    if (!photoForm || !form || !box) return;
    const fields = form.querySelectorAll('input[type="number"]');
    const tokenInput = form.elements.namedItem("reading_token");

    let currentPhoto = null;
    let revision = 0;
    let controller = null;
    let busy = false;

    function clearReview() {
        if (reviewBox) reviewBox.hidden = true;
        if (reviewForm) reviewForm.elements.namedItem("confirmation_id").value = "";
    }

    function showMessage(text, kind) {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function setBusy(value) {
        busy = value;
        button.disabled = value;
        fields.forEach((field) => { field.disabled = value; });
        button.textContent = value ? "Confirmando..." : "Confirmar números";
        form.setAttribute("aria-busy", String(value));
        photoForm.dispatchEvent(new CustomEvent("confirmation:busy", {
            detail: { busy: value },
        }));
    }

    function resetConfirmation() {
        clearReview();
        revision += 1;
        controller?.abort();
        controller = null;
        currentPhoto = null;
        form.reset();
        tokenInput.value = "";
        box.hidden = true;
        message.hidden = true;
        setBusy(false);
    }

    photoForm.addEventListener("photo:reset", resetConfirmation);
    photoForm.addEventListener("photo:validated", (event) => {
        resetConfirmation();
        const { file, reading, token } = event.detail;
        if (!reading?.can_confirm || !token) return;
        currentPhoto = file;
        tokenInput.value = token;
        fields.forEach((field) => {
            const value = reading.propuesta[field.name];
            // El cero es una lectura válida, no un campo vacío.
            field.value = Number.isInteger(value) ? String(value) : "";
        });
        box.hidden = false;
    });
    form.addEventListener("input", () => { message.hidden = true; clearReview(); });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (busy) return;
        if (!currentPhoto || !tokenInput.value) {
            showMessage("Primero carga una fotografía para leer sus números.", "danger");
            return;
        }
        const requestRevision = revision;
        const data = new FormData(form);
        data.set("photo", currentPhoto);
        const requestController = new AbortController();
        controller = requestController;
        message.hidden = true;
        clearReview();
        setBusy(true);
        try {
            const response = await fetch(form.action, {
                method: "POST", body: data, signal: requestController.signal,
            });
            if (requestRevision !== revision) return;
            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("application/json")) {
                showMessage("Actualiza la página y vuelve a cargar la fotografía.", "danger");
                return;
            }
            const result = await response.json();
            if (requestRevision !== revision) return;
            if (!response.ok) {
                showMessage(result.error || "No se pudieron confirmar los números.", "danger");
                return;
            }
            fields.forEach((field) => { field.value = result.confirmed[field.name]; });
            showMessage("Lectura confirmada. El resultado escrito es " +
                result.confirmed.written_result +
                ". Ya puedes comprobar tu suma.", "info");
            if (reviewBox && reviewForm && result.confirmed.confirmation_id) {
                reviewForm.elements.namedItem("confirmation_id").value = result.confirmed.confirmation_id;
                reviewBox.hidden = false;
            }
        } catch (error) {
            if (requestRevision !== revision || error.name === "AbortError") return;
            showMessage("No se pudo completar la confirmación. Vuelve a intentarlo.", "danger");
        } finally {
            if (requestRevision === revision) {
                controller = null;
                setBusy(false);
            }
        }
    });
})();
