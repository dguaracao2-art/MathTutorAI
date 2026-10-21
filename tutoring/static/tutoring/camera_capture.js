(() => {
    const openButton = document.getElementById("open-camera");
    const captureButton = document.getElementById("capture-photo");
    const closeButton = document.getElementById("close-camera");
    const box = document.getElementById("camera-box");
    const video = document.getElementById("camera-video");
    const message = document.getElementById("camera-message");
    const form = document.getElementById("photo-form");
    const input = document.getElementById("id_photo");

    let stream = null;
    let sequence = 0;

    function showMessage(text, kind = "info") {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function stopCamera() {
        sequence += 1;

        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }

        video.pause();
        video.srcObject = null;
        box.hidden = true;
        openButton.disabled = false;
        captureButton.disabled = true;
    }

    openButton.addEventListener("click", async () => {
        if (input.disabled) {
            showMessage("Espera a que termine la carga actual.");
            return;
        }

        if (
            !window.isSecureContext ||
            !navigator.mediaDevices?.getUserMedia
        ) {
            showMessage(
                "Usa la dirección local del aplicativo o una " +
                "conexión HTTPS para abrir la cámara.",
                "danger"
            );
            return;
        }

        const requestId = ++sequence;
        openButton.disabled = true;
        captureButton.disabled = true;
        box.hidden = false;

        showMessage(
            "Permite el acceso a la cámara cuando lo solicite el navegador."
        );

        try {
            const newStream = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: {
                    facingMode: { ideal: "environment" },
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                },
            });

            if (requestId !== sequence) {
                newStream.getTracks().forEach((track) => track.stop());
                return;
            }

            stream = newStream;
            video.srcObject = stream;

            stream.getVideoTracks()[0].addEventListener("ended", () => {
                if (requestId === sequence) {
                    stopCamera();
                    showMessage(
                        "La cámara se desconectó. Puedes abrirla nuevamente.",
                        "danger"
                    );
                }
            });

            await video.play();

            if (requestId !== sequence) return;

            captureButton.disabled = false;

            showMessage(
                "Coloca una sola suma completa dentro del recuadro " +
                "y pulsa Capturar foto."
            );
        } catch (error) {
            if (requestId !== sequence) return;

            stopCamera();

            const errors = {
                NotAllowedError:
                    "El acceso a la cámara está bloqueado. " +
                    "Revisa sus permisos.",
                NotFoundError:
                    "No se encontró una cámara disponible. " +
                    "Puedes cargar una fotografía.",
                NotReadableError:
                    "No se pudo abrir la cámara. Cierra otras " +
                    "aplicaciones que la estén usando.",
            };

            showMessage(
                errors[error.name] ||
                "No se pudo abrir la cámara. Inténtalo nuevamente.",
                "danger"
            );
        }
    });

    captureButton.addEventListener("click", () => {
        if (input.disabled) {
            showMessage("Espera a que termine la carga actual.");
            return;
        }

        if (!stream || video.readyState < 2 || !video.videoWidth) {
            showMessage("Espera a que aparezca la imagen de la cámara.");
            return;
        }

        const canvas = document.createElement("canvas");
        const scale = Math.min(
            1,
            1920 / Math.max(video.videoWidth, video.videoHeight)
        );

        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);

        const context = canvas.getContext("2d");

        if (!context) {
            showMessage("No se pudo preparar la fotografía.", "danger");
            return;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        const requestId = sequence;
        captureButton.disabled = true;

        canvas.toBlob((blob) => {
            if (requestId !== sequence) return;

            captureButton.disabled = false;

            if (!blob) {
                showMessage(
                    "No se pudo capturar la foto. Inténtalo otra vez.",
                    "danger"
                );
                return;
            }

            if (input.disabled) {
                showMessage(
                    "Espera a que termine la carga actual y captura otra vez."
                );
                return;
            }

            try {
                const file = new File(
                    [blob],
                    "captura-suma.jpg",
                    { type: "image/jpeg" }
                );

                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;

                input.dispatchEvent(
                    new Event("change", { bubbles: true })
                );

                showMessage("Fotografía tomada.");
                form.requestSubmit();
            } catch {
                showMessage(
                    "No se pudo preparar la captura. " +
                    "Puedes seleccionar una fotografía.",
                    "danger"
                );
            }
        }, "image/jpeg", 0.9);
    });

    closeButton.addEventListener("click", () => {
        stopCamera();
        showMessage("Cámara cerrada.");
    });

    input.addEventListener("change", stopCamera);
    form.addEventListener("submit", stopCamera);
    window.addEventListener("pagehide", stopCamera);

    document.addEventListener("visibilitychange", () => {
        if (document.hidden && !box.hidden) {
            stopCamera();
            showMessage("Cámara cerrada. Puedes abrirla nuevamente.");
        }
    });
})();
