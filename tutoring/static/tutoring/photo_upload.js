(() => {
    const form = document.getElementById("photo-form");
    const input = document.getElementById("id_photo");
    const button = document.getElementById("upload-button");
    const message = document.getElementById("photo-message");
    const previewBox = document.getElementById("photo-preview-box");
    const previewImage = document.getElementById("photo-preview");
    if (!form || !input || !button) return;

    let previewUrl = null;
    let revision = 0;
    let controller = null;
    let uploading = false;
    let confirming = false;

    function showMessage(text, kind) {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function updateControls() {
        button.disabled = uploading || confirming;
        input.disabled = uploading || confirming;
        button.textContent = uploading ? "Leyendo fotografía..." : "Cargar y leer fotografía";
        form.setAttribute("aria-busy", String(uploading));
    }

    function resetPhoto() {
        revision += 1;
        controller?.abort();
        controller = null;
        uploading = false;
        previewBox.hidden = true;
        previewImage.removeAttribute("src");
        if (previewUrl !== null) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
        message.hidden = true;
        form.dispatchEvent(new Event("photo:reset"));
        updateControls();
    }

    input.addEventListener("change", resetPhoto);
    window.addEventListener("pagehide", resetPhoto);
    form.addEventListener("confirmation:busy", (event) => {
        confirming = event.detail.busy;
        updateControls();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (uploading || confirming) return;
        resetPhoto();
        const file = input.files[0];
        if (!file) {
            showMessage("Selecciona una fotografía.", "danger");
            return;
        }

        const requestRevision = revision;
        const data = new FormData(form);
        const requestController = new AbortController();
        controller = requestController;
        uploading = true;
        updateControls();
        showMessage("Leyendo tu fotografía. Espera a que aparezcan los números.", "info");

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
            if (!response.ok || !result.ok) {
                showMessage(result.error || "No se pudo leer la fotografía.", "danger");
                return;
            }

            previewUrl = URL.createObjectURL(file);
            previewImage.src = previewUrl;
            previewBox.hidden = false;
            const reading = result.reading;
            if (!reading) {
                showMessage("No llegó una lectura. Actualiza la página y vuelve a cargar la foto.", "warning");
                return;
            }
            if (reading.can_confirm && result.reading_token) {
                form.dispatchEvent(new CustomEvent("photo:validated", {
                    detail: { file, reading, token: result.reading_token },
                }));
            }
            showMessage(reading.mensaje,
                reading.estado === "pendiente_de_confirmacion" ? "info" : "warning");
        } catch (error) {
            if (requestRevision !== revision || error.name === "AbortError") return;
            showMessage("No se pudo conectar con el servidor. Vuelve a intentarlo.", "danger");
        } finally {
            if (requestRevision === revision) {
                uploading = false;
                controller = null;
                updateControls();
            }
        }
    });
})();
