(() => {
    const openButton = document.getElementById("open-camera");
    const captureButton = document.getElementById("capture-photo");
    const closeButton = document.getElementById("close-camera");
    const box = document.getElementById("camera-box");
    const video = document.getElementById("camera-video");
    const frame = document.getElementById("camera-frame");
    const guide = document.getElementById("camera-guide");
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

            // Mantener el marco y el video con la misma proporción: sin
            // letterboxing, las coordenadas visibles coinciden con la captura.
            const ratio = video.videoWidth / video.videoHeight;
            if (!Number.isFinite(ratio) || ratio <= 0) {
                throw new Error("La cámara aún no entrega una imagen.");
            }
            frame.style.aspectRatio = String(ratio);
            frame.style.maxWidth = (320 * ratio) + "px";
            captureButton.disabled = false;

            showMessage(
                "Se capturará solo el interior del marco azul. " +
                "Acerca la hoja, espera a verla nítida y pulsa Capturar foto."
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

        const visibleVideo = video.getBoundingClientRect();
        const visibleGuide = guide.getBoundingClientRect();
        if (!visibleVideo.width || !visibleVideo.height ||
                !visibleGuide.width || !visibleGuide.height) {
            showMessage("Espera a que el marco de la cámara esté visible.");
            return;
        }
        // El marco puede cambiar de tamaño en móvil. Usar sus coordenadas
        // actuales, no la resolución CSS ni números del ejercicio elegido.
        const sx = Math.max(0, Math.round(
            (visibleGuide.left - visibleVideo.left) * video.videoWidth / visibleVideo.width
        ));
        const sy = Math.max(0, Math.round(
            (visibleGuide.top - visibleVideo.top) * video.videoHeight / visibleVideo.height
        ));
        const sw = Math.min(video.videoWidth - sx, Math.round(
            visibleGuide.width * video.videoWidth / visibleVideo.width
        ));
        const sh = Math.min(video.videoHeight - sy, Math.round(
            visibleGuide.height * video.videoHeight / visibleVideo.height
        ));
        if (sw <= 0 || sh <= 0) {
            showMessage("No se pudo delimitar la suma. Abre la cámara nuevamente.", "danger");
            return;
        }
        const canvas = document.createElement("canvas");
        // PNG evita otra compresión JPEG. Limitar píxeles también limita peso.
        const scale = Math.min(1, 1920 / Math.max(sw, sh),
            Math.sqrt(1500000 / (sw * sh)));
        canvas.width = Math.max(1, Math.round(sw * scale));
        canvas.height = Math.max(1, Math.round(sh * scale));

        const context = canvas.getContext("2d");

        if (!context) {
            showMessage("No se pudo preparar la fotografía.", "danger");
            return;
        }

        context.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);

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

            if (blob.size > 5 * 1024 * 1024) {
                showMessage("La captura supera los 5 MB. Selecciona otra fotografía.", "danger");
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
                    "captura-suma.png",
                    { type: "image/png" }
                );

                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;

                input.dispatchEvent(
                    new Event("change", { bubbles: true })
                );

                showMessage(
                    "Foto tomada. Revisa la vista previa. Si está oscura, cortada " +
                    "o borrosa, abre la cámara y repítela. Si se ve bien, pulsa " +
                    "Cargar y leer fotografía."
                );
            } catch {
                showMessage(
                    "No se pudo preparar la captura. " +
                    "Puedes seleccionar una fotografía.",
                    "danger"
                );
            }
        }, "image/png");
    });

    closeButton.addEventListener("click", () => {
        stopCamera();
        showMessage("Cámara cerrada.");
    });

    input.addEventListener("change", () => {
        stopCamera();
        message.hidden = true;
    });
    form.addEventListener("submit", () => {
        stopCamera();
        message.hidden = true;
    });
    window.addEventListener("pagehide", stopCamera);

    document.addEventListener("visibilitychange", () => {
        if (document.hidden && !box.hidden) {
            stopCamera();
            showMessage("Cámara cerrada. Puedes abrirla nuevamente.");
        }
    });
})();
