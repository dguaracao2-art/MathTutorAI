/* Contrato de captura: región visible, revisión previa y cierre de la cámara. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function cameraPage({deny = false, delayBlob = false, width = 1280, height = 720} = {}) {
    class Element extends EventTarget {
        constructor() { super(); this.style = {}; this.files = []; this.disabled = false; }
    }
    const ids = ['open-camera', 'capture-photo', 'close-camera', 'camera-box',
        'camera-video', 'camera-frame', 'camera-guide', 'camera-message', 'photo-form', 'id_photo'];
    const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
    const video = elements['camera-video'];
    let stops = 0, submits = 0, blobCallback, drawArgs, mime;
    const track = new EventTarget();
    track.stop = () => stops++;
    const stream = {getTracks: () => [track], getVideoTracks: () => [track]};
    Object.assign(video, {videoWidth: width, videoHeight: height, readyState: 3,
        play: async () => {}, pause: () => {},
        getBoundingClientRect: () => ({left: 20, top: 30, width: 400, height: 225})});
    elements['camera-guide'].getBoundingClientRect = () =>
        ({left: 100, top: 48, width: 240, height: 189});
    elements['photo-form'].requestSubmit = () => submits++;
    const canvas = {getContext: () => ({drawImage: (...args) => { drawArgs = args; }}),
        toBlob(callback, type) {
            mime = type;
            blobCallback = callback;
            if (!delayBlob) callback(new Blob(['pixeles'], {type}));
        }};
    const document = new EventTarget();
    Object.assign(document, {getElementById: id => elements[id], createElement: () => canvas});
    const window = new EventTarget();
    window.isSecureContext = true;
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,
        '../tutoring/static/tutoring/camera_capture.js'), 'utf8'), {
        document, window, navigator: {mediaDevices: {getUserMedia: async () => {
            if (deny) throw Object.assign(new Error('denegado'), {name: 'NotAllowedError'});
            return stream;
        }}}, Event, File, DataTransfer: class {
            constructor() {
                this.files = [];
                this.items = {add: file => this.files.push(file)};
            }
        },
    });
    return {elements, window, canvas, get stops() {return stops;},
        get submits() {return submits;}, get drawArgs() {return drawArgs;}, get mime() {return mime;},
        click: id => elements[id].dispatchEvent(new Event('click')),
        finishBlob: () => blobCallback(new Blob(['pixeles'], {type: 'image/png'})),
        async open() { this.click('open-camera'); await new Promise(setImmediate); },
    };
}

test('captura los píxeles correspondientes al marco visible y espera revisión antes del OCR', async () => {
    const p = cameraPage();
    await p.open();
    p.click('capture-photo');
    assert.deepEqual(p.drawArgs.slice(1), [256, 58, 768, 605, 0, 0, 768, 605]);
    assert.equal(p.mime, 'image/png');
    assert.equal(p.elements.id_photo.files[0].name, 'captura-suma.png');
    assert.equal(p.submits, 0);
    assert.equal(p.stops, 1);
    assert.match(p.elements['camera-message'].textContent, /Revisa la vista previa/);
});

test('la captura grande respeta el límite de píxeles sin ampliar una imagen pequeña', async () => {
    const p = cameraPage({width: 3840, height: 2160});
    await p.open();
    p.click('capture-photo');
    assert.ok(p.canvas.width * p.canvas.height < 1503000);
    assert.ok(Math.max(p.canvas.width, p.canvas.height) <= 1920);
});

test('cerrar la cámara mientras se prepara PNG descarta la captura pendiente', async () => {
    const p = cameraPage({delayBlob: true});
    await p.open();
    p.click('capture-photo');
    p.click('close-camera');
    p.finishBlob();
    assert.equal(p.elements.id_photo.files.length, 0);
    assert.equal(p.stops, 1);
});

test('denegar permiso conserva la alternativa de seleccionar un archivo', async () => {
    const p = cameraPage({deny: true});
    await p.open();
    assert.match(p.elements['camera-message'].textContent, /bloqueado/);
    assert.equal(p.elements['open-camera'].disabled, false);
    assert.equal(p.elements.id_photo.disabled, false);
    assert.equal(p.elements.id_photo.files.length, 0);
});

test('salir de la página apaga los tracks activos', async () => {
    const p = cameraPage();
    await p.open();
    p.window.dispatchEvent(new Event('pagehide'));
    assert.equal(p.stops, 1);
    assert.equal(p.elements['camera-box'].hidden, true);
});
