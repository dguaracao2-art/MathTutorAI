(() => {
    const photoForm = document.getElementById("photo-form");
    const photoInput = document.getElementById("id_photo");
    const uploadButton = document.getElementById("upload-button");
    const box = document.getElementById("confirmation-box");
    const form = document.getElementById("confirmation-form");
    const button = document.getElementById("confirm-button");
    const message = document.getElementById("confirmation-message");
    const fields = form.querySelectorAll('input[type="number"]');

    let currentPhoto = null;
    let revision = 0;

    function showMessage(text, kind) {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function resetConfirmation() {
        revision += 1;
        currentPhoto = null;
        form.reset();
        box.hidden = true;
        message.hidden = true;
    }

    function setBusy(busy) {
        button.disabled = busy;
        photoInput.disabled = busy;
        uploadButton.disabled = busy;

        fields.forEach((field) => {
            field.disabled = busy;
        });

        button.textContent = busy
            ? "Confirmando..."
            : "Confirmar números";
    }

    photoForm.addEventListener("photo:reset", resetConfirmation);

    photoForm.addEventListener("photo:validated", (event) => {
        resetConfirmation();
        currentPhoto = event.detail.file;
        box.hidden = false;
    });

    form.addEventListener("input", () => {
        message.hidden = true;
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (button.disabled) return;

        if (!currentPhoto) {
            showMessage(
                "Primero carga una fotografía válida.",
                "danger"
            );
            return;
        }

        const requestRevision = revision;
        const data = new FormData(form);
        data.set("photo", currentPhoto);

        message.hidden = true;
        setBusy(true);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: data,
            });

            const contentType =
                response.headers.get("content-type") || "";

            if (requestRevision !== revision) return;

            if (!contentType.includes("application/json")) {
                showMessage(
                    "Actualiza la página y vuelve a confirmar los números.",
                    "danger"
                );
                return;
            }

            const result = await response.json();

            if (requestRevision !== revision) return;

            if (!response.ok) {
                showMessage(
                    result.error || "No se pudieron confirmar los números.",
                    "danger"
                );
                return;
            }

            fields.forEach((field) => {
                field.value = result.confirmed[field.name];
            });

            showMessage(
                "Números confirmados. El resultado escrito es " +
                result.confirmed.written_result + ".",
                "success"
            );
        } catch {
            if (requestRevision === revision) {
                showMessage(
                    "No se pudo completar la confirmación. " +
                    "Vuelve a intentarlo.",
                    "danger"
                );
            }
        } finally {
            setBusy(false);
        }
    });
})();