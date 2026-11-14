(() => {
    const openButton = document.getElementById("open-camera");
    const captureButton = document.getElementById("capture-photo");
    const closeButton = document.getElementById("close-camera");
    const autoToggle = document.getElementById("auto-capture");
    const box = document.getElementById("camera-box");
    const video = document.getElementById("camera-video");
    const frame = document.getElementById("camera-frame");
    const guide = document.getElementById("camera-guide");
    const overlay = document.getElementById("camera-overlay");
    const status = document.getElementById("camera-status");
    const message = document.getElementById("camera-message");
    const form = document.getElementById("photo-form");
    const input = document.getElementById("id_photo");

    if (!openButton || !video || !frame || !guide || !form || !input) return;

    // Ritmo de envío de cuadros de guía. El servidor descarta lo que llegue
    // por encima de su propio límite, así que este valor solo evita trabajo
    // inútil en el navegador y tráfico de más.
    const INTERVALO_ENVIO = 180;
    // Ancho del cuadro que se envía. El detector localiza filas, no cifras:
    // no necesita resolución de lectura y a 480 px responde mucho antes.
    const ANCHO_GUIA = 480;
    // Cuántas detecciones seguidas bien encuadradas y quietas hacen falta
    // para disparar la captura sola.
    const DETECCIONES_PARA_CAPTURAR = 6;
    // Desplazamiento máximo, en fracción del recorte, para considerar que la
    // hoja sigue quieta entre dos detecciones.
    const MOVIMIENTO_MAXIMO = 0.03;
    // Margen que deben dejar las filas respecto al borde del recorte. Si una
    // fila lo toca, es probable que la suma esté cortada.
    const MARGEN_BORDE = 0.02;
    // Altura mínima del conjunto de las tres filas dentro del recorte. Por
    // debajo, la hoja está lejos y el lector recibiría cifras diminutas.
    const ALTURA_MINIMA = 0.35;
    // Margen que se añade alrededor de las filas detectadas al recortar la
    // fotografía definitiva, en fracción del tamaño de esas filas. Deja aire
    // para los trazos que sobresalgan del borde de una caja.
    const MARGEN_RECORTE = 0.08;
    // Cuánto vale una detección para recortar con ella. Pasado ese tiempo la
    // hoja pudo moverse y se vuelve a capturar el marco entero.
    const VIGENCIA_DETECCION = 1500;

    let stream = null;
    let sequence = 0;
    let canal = null;
    let temporizador = null;
    let enviando = false;
    let lienzoGuia = null;
    let detector = "desconocido";
    let estables = 0;
    let ultimoEncuadre = null;
    let ultimaDeteccion = null;
    let capturando = false;

    function showMessage(text, kind = "info") {
        message.textContent = text;
        message.className = "alert alert-" + kind + " mt-3";
        message.hidden = false;
    }

    function setStatus(texto, estado) {
        if (!status) return;
        status.textContent = texto;
        status.dataset.estado = estado;
    }

    function marcarMarco(valor) {
        if (valor) {
            frame.dataset.deteccion = valor;
        } else {
            delete frame.dataset.deteccion;
        }
    }

    // ------------------------------------------------------------------
    // Geometría: el marco azul, en píxeles del video y en fracción del cuadro
    // ------------------------------------------------------------------

    function regionDelMarco() {
        // El marco puede cambiar de tamaño según la ventana. Se leen sus
        // coordenadas actuales, no valores fijos del estilo.
        if (!video.videoWidth || !video.videoHeight) return null;
        const areaVideo = video.getBoundingClientRect();
        const areaGuia = guide.getBoundingClientRect();
        if (!areaVideo.width || !areaVideo.height ||
                !areaGuia.width || !areaGuia.height) {
            return null;
        }
        const sx = Math.max(0, Math.round(
            (areaGuia.left - areaVideo.left) * video.videoWidth / areaVideo.width
        ));
        const sy = Math.max(0, Math.round(
            (areaGuia.top - areaVideo.top) * video.videoHeight / areaVideo.height
        ));
        const sw = Math.min(video.videoWidth - sx, Math.round(
            areaGuia.width * video.videoWidth / areaVideo.width
        ));
        const sh = Math.min(video.videoHeight - sy, Math.round(
            areaGuia.height * video.videoHeight / areaVideo.height
        ));
        if (sw <= 0 || sh <= 0) return null;
        return { sx, sy, sw, sh };
    }

    function regionDeCaptura() {
        // Recortar lo que el detector acaba de localizar, no todo el marco.
        //
        // Medido con fotografías de un cuaderno con varias sumas: cuando en
        // el recorte entran operaciones vecinas, el lector falla o devuelve
        // cifras de otra suma; con el recorte ajustado a una sola, acierta.
        // El detector ya sabe dónde están las tres filas, así que se usa esa
        // información para encuadrar en lugar de confiar en el pulso.
        //
        // Si no hay detección reciente —el detector no está, la hoja se movió
        // o el usuario captura a mano sin guía— se recorta el marco entero,
        // que es el comportamiento anterior.
        const marco = regionDelMarco();
        if (marco === null) return null;
        if (ultimaDeteccion === null) return marco;
        if (performance.now() - ultimaDeteccion.momento > VIGENCIA_DETECCION) {
            return marco;
        }

        const area = ultimaDeteccion.area;
        const ancho = area.x2 - area.x1;
        const alto = area.y2 - area.y1;
        if (ancho <= 0 || alto <= 0) return marco;

        const margenX = ancho * MARGEN_RECORTE;
        const margenY = alto * MARGEN_RECORTE;
        const x1 = Math.max(0, area.x1 - margenX);
        const y1 = Math.max(0, area.y1 - margenY);
        const x2 = Math.min(1, area.x2 + margenX);
        const y2 = Math.min(1, area.y2 + margenY);

        const sx = Math.round(marco.sx + x1 * marco.sw);
        const sy = Math.round(marco.sy + y1 * marco.sh);
        const sw = Math.round((x2 - x1) * marco.sw);
        const sh = Math.round((y2 - y1) * marco.sh);
        if (sw <= 0 || sh <= 0) return marco;
        return { sx, sy, sw, sh };
    }

    function guiaEnElMarco() {
        const areaFrame = frame.getBoundingClientRect();
        const areaGuia = guide.getBoundingClientRect();
        if (!areaFrame.width || !areaFrame.height) return null;
        return {
            x: (areaGuia.left - areaFrame.left) / areaFrame.width,
            y: (areaGuia.top - areaFrame.top) / areaFrame.height,
            w: areaGuia.width / areaFrame.width,
            h: areaGuia.height / areaFrame.height,
        };
    }

    // ------------------------------------------------------------------
    // Capa de dibujo
    // ------------------------------------------------------------------

    function limpiarOverlay() {
        if (!overlay) return;
        const contexto = overlay.getContext("2d");
        if (contexto) contexto.clearRect(0, 0, overlay.width, overlay.height);
    }

    function dibujarFilas(filas) {
        if (!overlay) return;
        const ancho = frame.clientWidth;
        const alto = frame.clientHeight;
        if (!ancho || !alto) return;
        if (overlay.width !== ancho) overlay.width = ancho;
        if (overlay.height !== alto) overlay.height = alto;

        const contexto = overlay.getContext("2d");
        if (!contexto) return;
        contexto.clearRect(0, 0, ancho, alto);

        // Las filas llegan en fracciones del recorte, no del cuadro completo:
        // hay que situarlas dentro del marco antes de dibujarlas.
        const g = guiaEnElMarco();
        if (!g) return;

        contexto.lineWidth = 2;
        contexto.strokeStyle = "#22c55e";
        contexto.fillStyle = "#22c55e22";

        Object.values(filas).forEach((fila) => {
            const x = (g.x + fila.x * g.w) * ancho;
            const y = (g.y + fila.y * g.h) * alto;
            const w = fila.w * g.w * ancho;
            const h = fila.h * g.h * alto;
            contexto.fillRect(x, y, w, h);
            contexto.strokeRect(x, y, w, h);
        });
    }

    // ------------------------------------------------------------------
    // Encuadre y estabilidad
    // ------------------------------------------------------------------

    function envolvente(filas) {
        const valores = Object.values(filas);
        if (!valores.length) return null;
        return {
            x1: Math.min(...valores.map((f) => f.x)),
            y1: Math.min(...valores.map((f) => f.y)),
            x2: Math.max(...valores.map((f) => f.x + f.w)),
            y2: Math.max(...valores.map((f) => f.y + f.h)),
        };
    }

    function tocaElBorde(area) {
        return (
            area.x1 < MARGEN_BORDE ||
            area.y1 < MARGEN_BORDE ||
            area.x2 > 1 - MARGEN_BORDE ||
            area.y2 > 1 - MARGEN_BORDE
        );
    }

    function sigueQuieta(area, anterior) {
        if (!anterior) return false;
        return (
            Math.abs(area.x1 - anterior.x1) < MOVIMIENTO_MAXIMO &&
            Math.abs(area.y1 - anterior.y1) < MOVIMIENTO_MAXIMO &&
            Math.abs(area.x2 - anterior.x2) < MOVIMIENTO_MAXIMO &&
            Math.abs(area.y2 - anterior.y2) < MOVIMIENTO_MAXIMO
        );
    }

    function evaluarDeteccion(filas) {
        dibujarFilas(filas);

        const area = envolvente(filas);
        if (!area) return;

        if (tocaElBorde(area)) {
            estables = 0;
            ultimoEncuadre = area;
            ultimaDeteccion = null;
            marcarMarco("parcial");
            setStatus(
                "La suma se sale del marco. Aleja un poco la cámara.",
                "buscando"
            );
            return;
        }

        if (area.y2 - area.y1 < ALTURA_MINIMA) {
            estables = 0;
            ultimoEncuadre = area;
            ultimaDeteccion = null;
            marcarMarco("parcial");
            setStatus(
                "La suma se ve pequeña. Acerca la cámara a la hoja.",
                "buscando"
            );
            return;
        }

        estables = sigueQuieta(area, ultimoEncuadre) ? estables + 1 : 1;
        ultimoEncuadre = area;
        // Solo se guarda para recortar cuando el encuadre es válido: así
        // nunca se recorta por unas filas que estaban cortadas o lejanas.
        ultimaDeteccion = { area, momento: performance.now() };
        marcarMarco("lista");

        if (!autoToggle || !autoToggle.checked) {
            setStatus("Suma completa en el marco. Pulsa Capturar foto.", "lista");
            return;
        }

        if (estables >= DETECCIONES_PARA_CAPTURAR) {
            setStatus("Hoja estable. Capturando...", "lista");
            capturar(true);
            return;
        }

        const resto = DETECCIONES_PARA_CAPTURAR - estables;
        setStatus(
            "Suma completa. Mantén la hoja quieta (" + resto + ")...",
            "lista"
        );
    }

    // ------------------------------------------------------------------
    // Canal en tiempo real
    // ------------------------------------------------------------------

    function cerrarCanal() {
        if (temporizador !== null) {
            clearInterval(temporizador);
            temporizador = null;
        }
        if (canal) {
            canal.onopen = canal.onmessage = canal.onerror = canal.onclose = null;
            if (canal.readyState === WebSocket.OPEN ||
                    canal.readyState === WebSocket.CONNECTING) {
                canal.close();
            }
            canal = null;
        }
        enviando = false;
        estables = 0;
        ultimoEncuadre = null;
        ultimaDeteccion = null;
        limpiarOverlay();
        marcarMarco(null);
    }

    function enviarCuadro() {
        if (!canal || canal.readyState !== WebSocket.OPEN) return;
        if (enviando || capturando) return;
        if (!stream || video.readyState < 2 || !video.videoWidth) return;
        // bufferedAmount alto significa que la red no da abasto: saltar el
        // cuadro en lugar de acumular retraso en la guía.
        if (canal.bufferedAmount > 0) return;

        // Se envía únicamente el interior del marco. Si en la hoja hay otras
        // sumas alrededor, el detector no las ve y no puede confundirlas con
        // las filas de la operación que se está resolviendo.
        const region = regionDelMarco();
        if (region === null) return;

        if (lienzoGuia === null) lienzoGuia = document.createElement("canvas");
        const escala = Math.min(1, ANCHO_GUIA / region.sw);
        lienzoGuia.width = Math.max(1, Math.round(region.sw * escala));
        lienzoGuia.height = Math.max(1, Math.round(region.sh * escala));

        const contexto = lienzoGuia.getContext("2d");
        if (!contexto) return;
        contexto.drawImage(
            video,
            region.sx, region.sy, region.sw, region.sh,
            0, 0, lienzoGuia.width, lienzoGuia.height
        );

        enviando = true;
        lienzoGuia.toBlob(
            (blob) => {
                if (!blob || !canal || canal.readyState !== WebSocket.OPEN) {
                    enviando = false;
                    return;
                }
                blob.arrayBuffer()
                    .then((datos) => {
                        if (canal && canal.readyState === WebSocket.OPEN) {
                            canal.send(datos);
                        }
                    })
                    .catch(() => {})
                    .finally(() => { enviando = false; });
            },
            "image/jpeg",
            0.5
        );
    }

    function abrirCanal() {
        if (!window.WebSocket) {
            detector = "ausente";
            setStatus("Este navegador no admite la guía en tiempo real.", "inactivo");
            return;
        }

        const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
        const direccion = protocolo + "//" + window.location.host + "/ws/deteccion/";

        let nuevo;
        try {
            nuevo = new WebSocket(direccion);
        } catch {
            detector = "ausente";
            setStatus("Guía en tiempo real no disponible. Captura manual.", "inactivo");
            return;
        }

        canal = nuevo;
        setStatus("Conectando con la guía...", "buscando");

        nuevo.onopen = () => {
            if (canal !== nuevo) return;
            if (temporizador !== null) clearInterval(temporizador);
            temporizador = setInterval(enviarCuadro, INTERVALO_ENVIO);
        };

        nuevo.onmessage = (evento) => {
            if (canal !== nuevo) return;
            let carga;
            try {
                carga = JSON.parse(evento.data);
            } catch {
                return;
            }

            if (carga.estado === "sin_detector") {
                detector = "ausente";
                setStatus(
                    "Guía automática no disponible en este servidor. " +
                    "Encuadra la suma y pulsa Capturar foto.",
                    "inactivo"
                );
                cerrarCanal();
                return;
            }

            if (carga.estado === "listo") {
                detector = "activo";
                setStatus("Buscando la suma dentro del marco...", "buscando");
                return;
            }

            if (carga.estado === "buscando") {
                estables = 0;
                ultimoEncuadre = null;
                ultimaDeteccion = null;
                limpiarOverlay();
                marcarMarco(null);
                setStatus(
                    "No veo las tres filas dentro del marco. " +
                    "Encuadra una sola suma y mejora la luz.",
                    "buscando"
                );
                return;
            }

            if (carga.estado === "detectado" && carga.filas) {
                evaluarDeteccion(carga.filas);
            }
        };

        nuevo.onerror = () => {
            if (canal !== nuevo) return;
            setStatus("Guía interrumpida. Puedes capturar manualmente.", "error");
        };

        nuevo.onclose = (evento) => {
            if (canal !== nuevo) return;
            if (temporizador !== null) {
                clearInterval(temporizador);
                temporizador = null;
            }
            limpiarOverlay();
            marcarMarco(null);
            if (evento.code === 4401) {
                setStatus("Tu sesión expiró. Vuelve a iniciarla.", "error");
            } else if (detector !== "ausente") {
                setStatus("Guía desconectada. Puedes capturar manualmente.", "error");
            }
            canal = null;
        };
    }

    // ------------------------------------------------------------------
    // Cámara
    // ------------------------------------------------------------------

    function stopCamera() {
        sequence += 1;
        cerrarCanal();

        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }

        video.pause();
        video.srcObject = null;
        box.hidden = true;
        openButton.disabled = false;
        captureButton.disabled = true;
        capturando = false;
        setStatus("Detección en espera.", "inactivo");
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
            // letterboxing, las coordenadas visibles coinciden con la captura
            // y con las cajas que devuelve el detector.
            const ratio = video.videoWidth / video.videoHeight;
            if (!Number.isFinite(ratio) || ratio <= 0) {
                throw new Error("La cámara aún no entrega una imagen.");
            }
            frame.style.aspectRatio = String(ratio);
            if (window.matchMedia("(min-width: 992px)").matches) {
                frame.style.maxWidth = "100%";
            } else {
                frame.style.maxWidth = (320 * ratio) + "px";
            }
            captureButton.disabled = false;

            estables = 0;
            ultimoEncuadre = null;
            ultimaDeteccion = null;
            abrirCanal();

            showMessage(
                "Se envía y se captura solo el interior del marco. Encuadra " +
                "una sola suma: cuando el sistema vea las tres filas quietas, " +
                "toma la foto sola. También puedes pulsar Capturar foto."
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

    // ------------------------------------------------------------------
    // Captura a resolución completa
    // ------------------------------------------------------------------

    function capturar(automatica) {
        if (capturando) return;

        if (input.disabled) {
            showMessage("Espera a que termine la carga actual.");
            return;
        }

        if (!stream || video.readyState < 2 || !video.videoWidth) {
            showMessage("Espera a que aparezca la imagen de la cámara.");
            return;
        }

        const region = regionDeCaptura();
        if (region === null) {
            showMessage("Espera a que el marco de la cámara esté visible.");
            return;
        }

        const ajustada = ultimaDeteccion !== null &&
            performance.now() - ultimaDeteccion.momento <= VIGENCIA_DETECCION;
        const { sx, sy, sw, sh } = region;
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
        capturando = true;
        captureButton.disabled = true;

        canvas.toBlob((blob) => {
            if (requestId !== sequence) { capturando = false; return; }

            captureButton.disabled = false;

            if (!blob) {
                capturando = false;
                showMessage(
                    "No se pudo capturar la foto. Inténtalo otra vez.",
                    "danger"
                );
                return;
            }

            if (blob.size > 5 * 1024 * 1024) {
                capturando = false;
                showMessage("La captura supera los 5 MB. Selecciona otra fotografía.", "danger");
                return;
            }

            if (input.disabled) {
                capturando = false;
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

                // Este evento cierra la cámara y el canal: evita que la
                // captura automática se repita sobre la misma hoja.
                input.dispatchEvent(
                    new Event("change", { bubbles: true })
                );

                showMessage(
                    (automatica
                        ? "Foto tomada sola al ver la suma quieta. "
                        : "Foto tomada. ") +
                    (ajustada
                        ? "Recortada a las filas detectadas, sin las sumas de al lado. "
                        : "") +
                    "Revisa la vista previa. Si está oscura, cortada o borrosa, " +
                    "abre la cámara y repítela. Si se ve bien, pulsa " +
                    "Cargar y leer fotografía."
                );
            } catch {
                showMessage(
                    "No se pudo preparar la captura. " +
                    "Puedes seleccionar una fotografía.",
                    "danger"
                );
            } finally {
                capturando = false;
            }
        }, "image/png");
    }

    captureButton.addEventListener("click", () => capturar(false));

    closeButton.addEventListener("click", () => {
        stopCamera();
        showMessage("Cámara cerrada.");
    });

    if (autoToggle) {
        autoToggle.addEventListener("change", () => {
            estables = 0;
            ultimoEncuadre = null;
            if (!autoToggle.checked && detector === "activo") {
                setStatus("Captura automática desactivada.", "buscando");
            }
        });
    }

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