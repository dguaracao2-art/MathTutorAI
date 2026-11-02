/* Regresiones del flujo visible; usa solo módulos incluidos en Node.js. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function page(fetchImpl = () => { throw Error('No debe solicitar OCR.'); }) {
    class Element extends EventTarget {
        constructor() { super(); this.hidden = true; this.files = []; this.attrs = {}; }
        setAttribute(name, value) { this.attrs[name] = value; }
        removeAttribute(name) { delete this.attrs[name]; }
    }
    const ids = ['photo-form', 'id_photo', 'upload-button', 'photo-message',
        'photo-preview-box', 'photo-preview'];
    const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
    const revoked = [];
    let created = 0;
    const context = {
        document: { getElementById: id => elements[id] || null },
        window: new EventTarget(), Event, CustomEvent, AbortController,
        FormData: class {}, fetch: fetchImpl,
        URL: { createObjectURL: () => 'blob:prueba-' + (++created),
            revokeObjectURL: value => revoked.push(value) },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,
        '../tutoring/static/tutoring/photo_upload.js'), 'utf8'), context);
    return { elements, revoked, window: context.window,
        choose(file) {
            elements.id_photo.files = [file];
            elements.id_photo.dispatchEvent(new Event('change'));
        },
        submit() { elements['photo-form'].dispatchEvent(new Event('submit', {cancelable: true})); },
    };
}

test('la foto se muestra al seleccionarla, antes de pedir OCR', () => {
    const p = page();
    p.choose({name: 'suma.png'});
    assert.equal(p.elements['photo-preview-box'].hidden, false);
    assert.equal(p.elements['photo-preview'].src, 'blob:prueba-1');
});

test('la vista previa permanece visible mientras se lee y tras un error de separación', async () => {
    let finish;
    const p = page(() => new Promise(resolve => { finish = resolve; }));
    p.choose({name: 'suma.png'});
    p.submit();
    assert.equal(p.elements['photo-preview-box'].hidden, false);
    assert.equal(p.elements['upload-button'].disabled, true);
    finish({ok: true, headers: {get: () => 'application/json'}, json: async () => ({
        ok: true, reading: {can_confirm: false, estado: 'lectura_pendiente', mensaje: 'Toma otra foto.'},
    })});
    await new Promise(setImmediate);
    assert.equal(p.elements['photo-preview-box'].hidden, false);
    assert.equal(p.elements['upload-button'].disabled, false);
    assert.equal(p.elements['photo-message'].textContent, 'Toma otra foto.');
});

test('cambiar de foto y salir de la página revoca las vistas temporales anteriores', () => {
    const p = page();
    p.choose({name: 'primera.png'});
    p.choose({name: 'segunda.png'});
    assert.deepEqual(p.revoked, ['blob:prueba-1']);
    p.window.dispatchEvent(new Event('pagehide'));
    assert.deepEqual(p.revoked, ['blob:prueba-1', 'blob:prueba-2']);
    assert.equal(p.elements['photo-preview-box'].hidden, true);
});
