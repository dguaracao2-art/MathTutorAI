(() => {
    const form = document.getElementById("photo-form");
    const input = document.getElementById("id_photo");
    const button = document.getElementById("upload-button");
    const message = document.getElementById("photo-message");
    const previewBox = document.getElementById("photo-preview-box");
    const previewImage = document.getElementById("photo-preview");

    let previewUrl = null;

    function showMessage(text, kind) {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function clearPreview() {
    previewBox.hidden = true;
    previewImage.removeAttribute("src");

    if (previewUrl !== null) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
    }

    form.dispatchEvent(new Event("photo:reset"));
}

    input.addEventListener("change", () => {
        clearPreview();
        message.hidden = true;
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (button.disabled) return;

        clearPreview();
        message.hidden = true;

        const file = input.files[0];

        if (!file) {
            showMessage("Selecciona una fotografía.", "danger");
            return;
        }

        const data = new FormData(form);

        button.disabled = true;
        input.disabled = true;
        button.textContent = "Cargando...";

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: data,
            });

            const contentType =
                response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                showMessage(
                    "Actualiza la página y vuelve a cargar la fotografía.",
                    "danger"
                );
                return;
            }

            const result = await response.json();

            if (!response.ok) {
                showMessage(
                    result.error || "No se pudo cargar la fotografía.",
                    "danger"
                );
                return;
            }

            previewUrl = URL.createObjectURL(file);
            previewImage.src = previewUrl;
            previewBox.hidden = false;
            form.dispatchEvent(
    new CustomEvent("photo:validated", {
        detail: { file },
    })
);


            showMessage(
                "Fotografía cargada. Revisa que los dos números " +
                "y el resultado se vean completos.",
                "success"
            );
        } catch {
            showMessage(
                "No se pudo conectar con el servidor. Vuelve a intentarlo.",
                "danger"
            );
        } finally {
            button.disabled = false;
            input.disabled = false;
            button.textContent = "Cargar fotografía";
        }
    });
})();