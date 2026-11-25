/*
 * Tutoría en tiempo real por el canal /ws/tutoria/.
 *
 * Funciona en dos pantallas, según el atributo data-tutoria-vivo:
 *   "pistas"   -> revisión de la suma: «Ver pista» llega sin recargar.
 *   "progreso" -> «Mi progreso»: las tarjetas se actualizan solas.
 *
 * Es una mejora, no un requisito: si el navegador no tiene WebSocket, el
 * canal no abre o tarda en responder, el formulario se envía como siempre.
 */
(function () {
    "use strict";

    const raiz = document.querySelector("[data-tutoria-vivo]");
    if (!raiz || !window.WebSocket) return;

    const modo = raiz.dataset.tutoriaVivo;
    const indicador = raiz.querySelector("[data-vivo-indicador]");
    const ESPERA_RESPUESTA = 4000;
    const REINTENTOS = 5;

    let canal = null;
    let abierto = false;
    let reintentos = 0;
    let pendiente = null;

    function mostrarIndicador(visible) {
        if (indicador) indicador.hidden = !visible;
    }

    function conectar() {
        const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
        try {
            canal = new WebSocket(protocolo + "//" + window.location.host + "/ws/tutoria/");
        } catch (error) {
            return;
        }
        canal.addEventListener("open", function () {
            abierto = true;
            reintentos = 0;
            mostrarIndicador(true);
        });
        canal.addEventListener("close", function () {
            abierto = false;
            mostrarIndicador(false);
            if (pendiente) respaldo();
            if (reintentos < REINTENTOS) {
                const espera = 1000 * Math.pow(2, reintentos);
                reintentos += 1;
                window.setTimeout(conectar, espera);
            }
        });
        canal.addEventListener("message", function (evento) {
            let datos;
            try {
                datos = JSON.parse(evento.data);
            } catch (error) {
                return;
            }
            if (modo === "pistas") manejarPista(datos);
            if (modo === "progreso" && datos.tipo === "progreso") pintarProgreso(datos.registros || []);
        });
    }

    /* ---------- Pistas en vivo ---------- */

    function formulario() {
        return raiz.querySelector("form[data-pista]");
    }

    function respaldo() {
        // Ante cualquier duda, la vía de siempre: la vista HTTP decide.
        const form = pendiente || formulario();
        pendiente = null;
        if (form) form.submit();
    }

    function agregarPista(nivel, texto) {
        const lista = raiz.querySelector("[data-pistas]");
        if (!lista) return;
        const tarjeta = document.createElement("div");
        tarjeta.className = "alert hint-card";
        tarjeta.dataset.nivel = String(nivel);
        const titulo = document.createElement("h4");
        titulo.className = "h6";
        titulo.textContent = "Pista " + nivel;
        const parrafo = document.createElement("p");
        parrafo.className = "mb-0";
        parrafo.textContent = texto;
        tarjeta.appendChild(titulo);
        tarjeta.appendChild(parrafo);
        lista.appendChild(tarjeta);
        tarjeta.setAttribute("tabindex", "-1");
        tarjeta.focus();
    }

    function manejarPista(datos) {
        if (!pendiente) return;
        const form = pendiente;
        if (datos.tipo === "aviso") {
            respaldo();
            return;
        }
        if (datos.tipo !== "pista") return;
        pendiente = null;

        const yaMostrada = raiz.querySelector('[data-pistas] [data-nivel="' + datos.nivel + '"]');
        if (!yaMostrada) agregarPista(datos.nivel, datos.texto);

        const boton = form.querySelector("button");
        if (datos.siguiente) {
            form.querySelector('input[name="level"]').value = String(datos.siguiente);
            if (boton) {
                boton.textContent = "Ver pista " + datos.siguiente;
                boton.disabled = false;
            }
        } else {
            const fin = document.createElement("p");
            fin.className = "text-secondary";
            fin.textContent = "Ya viste las dos pistas. Corrige tu hoja y, si necesitas ayuda, pregúntale a tu profe.";
            form.replaceWith(fin);
        }
    }

    function prepararPistas() {
        const form = formulario();
        if (!form) return;
        form.addEventListener("submit", function (evento) {
            if (!abierto || !canal || canal.readyState !== WebSocket.OPEN) return;
            evento.preventDefault();
            if (pendiente) return;
            const nivel = parseInt(form.querySelector('input[name="level"]').value, 10);
            const confirmacion = form.querySelector('input[name="confirmation_id"]').value;
            const boton = form.querySelector("button");
            if (boton) boton.disabled = true;
            pendiente = form;
            canal.send(JSON.stringify({ accion: "pista", nivel: nivel, confirmation_id: confirmacion }));
            window.setTimeout(function () {
                if (pendiente === form) respaldo();
            }, ESPERA_RESPUESTA);
        });
    }

    /* ---------- Progreso en vivo ---------- */

    function parrafo(texto, clase) {
        const p = document.createElement("p");
        p.className = clase;
        p.textContent = texto;
        return p;
    }

    function pintarProgreso(registros) {
        const lista = raiz.querySelector("[data-progreso-lista]");
        if (!lista) return;
        lista.replaceChildren();
        if (!registros.length) {
            lista.appendChild(parrafo("Aún no tienes ejercicios registrados. ¡Revisa tu primera suma!", ""));
            return;
        }
        registros.forEach(function (registro, indice) {
            const tarjeta = document.createElement("article");
            tarjeta.className = "border rounded p-3";
            const titulo = document.createElement("h3");
            titulo.className = "h5";
            titulo.textContent = registro.exercise;
            tarjeta.appendChild(titulo);
            tarjeta.appendChild(parrafo("Último intento: " + registro.date, "mb-1 small"));
            tarjeta.appendChild(parrafo(registro.status, "mb-1 small"));
            tarjeta.appendChild(parrafo(
                "Intentos: " + registro.attempts + " · Pistas usadas: " + registro.hints,
                "mb-0 small"));
            if (indice === 0) {
                // La suma más reciente se resalta un momento para que se note el cambio.
                tarjeta.classList.add("border-primary");
                window.setTimeout(function () { tarjeta.classList.remove("border-primary"); }, 2500);
            }
            lista.appendChild(tarjeta);
        });
    }

    if (modo === "pistas") prepararPistas();
    conectar();
})();
