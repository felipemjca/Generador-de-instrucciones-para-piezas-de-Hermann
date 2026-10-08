(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const initial = JSON.parse($("#initial-payload").textContent);
  const state = structuredClone(initial);
  const pendingFiles = new Map();
  const previewUrls = new Map();
  let uidCounter = Date.now();
  let annotationEditor = null;
  let annotationLoadToken = 0;

  const uid = () => `u${uidCounter++}`;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
  const option = (value, selected, label = value) => `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? "selected" : ""}>${escapeHtml(label)}</option>`;
  state.sequences.forEach(s => {
    if (!s.uid) s.uid = uid();
    delete s.original_image_path;
    delete s.original_upload_key;
    s.annotation_data = {};
  });

  function previewUrl(uidValue, file) {
    const current = previewUrls.get(uidValue);
    if (current?.file === file) return current.url;
    if (current?.url) URL.revokeObjectURL(current.url);
    const url = URL.createObjectURL(file);
    previewUrls.set(uidValue, {file, url});
    return url;
  }

  function loadGeneral() {
    Object.entries(state.general || {}).forEach(([name, value]) => {
      const input = $(`[name="${name}"]`);
      if (input) input.value = value ?? "";
    });
    updateAutomaticDocument();
  }

  function updateAutomaticDocument() {
    const raw = ($('[name="station"]').value || "08").replace(/\D/g, "");
    const station = raw ? raw.padStart(2, "0") : "XX";
    $("#automatic-document").textContent = `SETEO ESTÁNDAR P${station} se agregará automáticamente.`;
  }

  function renderDocuments() {
    const root = $("#documents-list");
    root.innerHTML = state.documents.length ? state.documents.map((doc, i) => `
      <div class="repeat-item inline-grid" data-document="${i}">
        <label style="grid-column:span 5"><span>Documento adicional</span><input value="${escapeHtml(doc)}" data-field="document"></label>
        <button class="icon-button" type="button" data-remove="document" title="Eliminar">Eliminar</button>
      </div>`).join("") : `<p class="subtle">No hay documentos adicionales. El seteo estándar se incluye siempre.</p>`;
  }

  function renderSequences() {
    const root = $("#sequences-list");
    if (!state.sequences.length) {
      root.innerHTML = `<div class="empty"><h3>Agregá el primer paso</h3><p>La imagen es opcional. Los textos vacíos se guardarán como * Incompleto.</p></div>`;
      renderControls();
      return;
    }
    root.innerHTML = state.sequences.map((step, i) => {
      const preview = pendingFiles.has(step.uid) ? previewUrl(step.uid, pendingFiles.get(step.uid)) : (step.image_path ? `/uploads/${step.image_path}` : "");
      return `<article class="repeat-item sequence-item" data-sequence="${i}">
        <div class="repeat-head"><h3>Paso ${i + 1} · Hoja ${Math.floor(i / 5) + 1}${step.source_number && +step.source_number !== i + 1 ? ` · era N.º ${escapeHtml(step.source_number)}` : ""}</h3><div>
          <button class="icon-button" type="button" data-move="up" ${i === 0 ? "disabled" : ""}>↑</button>
          <button class="icon-button" type="button" data-move="down" ${i === state.sequences.length - 1 ? "disabled" : ""}>↓</button>
          <button class="icon-button" type="button" data-remove="sequence">Eliminar</button>
        </div></div>
        <div class="sequence-fields">
          <label class="wide"><span>Secuencia de trabajo</span><textarea rows="3" data-field="sequence" placeholder="Si queda vacío: * Incompleto">${escapeHtml(step.sequence)}</textarea></label>
          <label><span>Punto clave</span><textarea rows="2" data-field="key_point">${escapeHtml(step.key_point)}</textarea></label>
          <label><span>Razón del punto clave</span><textarea rows="2" data-field="reason">${escapeHtml(step.reason)}</textarea></label>
          <label class="wide"><span>Resumen para la hoja VISUAL</span><textarea rows="2" data-field="visual_summary" placeholder="Si queda vacío: * Incompleto">${escapeHtml(step.visual_summary)}</textarea></label>
          <div class="wide symbol-options"><div><strong>Indicadores en la celda del número</strong><p class="subtle">Todos son opcionales y se colocan debajo del número del paso.</p></div>
            <label class="check-option"><input type="checkbox" data-field="safety_symbol" ${step.safety_symbol ? "checked" : ""}><span>✚ Seguridad</span></label>
            <label class="check-option"><input type="checkbox" data-field="quality_symbol" ${step.quality_symbol ? "checked" : ""}><span>◇ Control de calidad</span></label>
            <label class="marker-number-field"><span>Número △S</span><input type="text" inputmode="numeric" pattern="[0-9]*" data-field="triangle_s_number" value="${escapeHtml(step.triangle_s_number)}" placeholder="Ej.: 4"></label>
          </div>
          <div class="wide"><label><span>Imagen opcional</span></label><div class="image-line">
            ${preview ? `<img class="image-preview" src="${escapeHtml(preview)}" alt="Vista previa">` : `<div class="image-preview" style="display:grid;place-items:center"><span class="subtle">SIN IMAGEN</span></div>`}
            <div><input type="file" accept="image/jpeg,image/png,image/bmp" data-image-input><p class="subtle">En VARIOS y VISUAL ocupará todo el recuadro asignado.</p><div class="image-actions">${preview ? `<button class="button secondary compact annotation-button" type="button" data-edit-image>Editar señaladores</button><button class="icon-button" type="button" data-remove-image>Quitar imagen</button>` : ""}</div></div>
          </div></div>
        </div>
      </article>`;
    }).join("");
    renderControls();
  }

  function annotationSnapshot() {
    if (!annotationEditor?.canvas) return JSON.stringify({version:1, width:0, height:0, objects:[]});
    const canvas = annotationEditor.canvas;
    return JSON.stringify({
      version: 1,
      width: canvas.width,
      height: canvas.height,
      objects: canvas.getObjects().map(object => object.toObject(["annotationType"])),
    });
  }

  function updateAnnotationButtons() {
    if (!annotationEditor) return;
    $("#annotation-undo").disabled = annotationEditor.historyIndex <= 0 || annotationEditor.busy;
    $("#annotation-redo").disabled = annotationEditor.historyIndex >= annotationEditor.history.length - 1 || annotationEditor.busy;
    $("#annotation-delete").disabled = !annotationEditor.canvas.getActiveObjects().length || annotationEditor.busy;
  }

  function rememberAnnotationState() {
    if (!annotationEditor || annotationEditor.restoring) return;
    const snapshot = annotationSnapshot();
    if (annotationEditor.history[annotationEditor.historyIndex] === snapshot) return;
    annotationEditor.history = annotationEditor.history.slice(0, annotationEditor.historyIndex + 1);
    annotationEditor.history.push(snapshot);
    if (annotationEditor.history.length > 50) annotationEditor.history.shift();
    annotationEditor.historyIndex = annotationEditor.history.length - 1;
    updateAnnotationButtons();
  }

  async function restoreAnnotationState(snapshot) {
    if (!annotationEditor) return;
    const canvas = annotationEditor.canvas;
    annotationEditor.restoring = true;
    canvas.discardActiveObject();
    canvas.remove(...canvas.getObjects());
    const data = JSON.parse(snapshot || "{}");
    const objects = await fabric.util.enlivenObjects(data.objects || []);
    if (objects.length) canvas.add(...objects);
    canvas.requestRenderAll();
    annotationEditor.restoring = false;
    updateAnnotationButtons();
  }

  function addAnnotationShape(kind) {
    if (!annotationEditor || annotationEditor.busy) return;
    const canvas = annotationEditor.canvas;
    const color = $("#annotation-color").value;
    const strokeWidth = +$("#annotation-width").value;
    const common = {stroke:color, strokeWidth, fill:"transparent", strokeUniform:true, cornerColor:"#c2185b", borderColor:"#c2185b", transparentCorners:false, annotationType:kind};
    const size = Math.max(60, Math.min(canvas.width, canvas.height) * .24);
    let shape;
    if (kind === "circle") {
      shape = new fabric.Circle({...common, radius:size / 2});
    } else if (kind === "rect") {
      shape = new fabric.Rect({...common, width:size * 1.25, height:size * .72, rx:4, ry:4});
    } else {
      shape = new fabric.Path("M 0 20 L 125 20 M 88 0 L 125 20 L 88 40", {...common, fill:null, strokeLineCap:"round", strokeLineJoin:"round"});
    }
    shape.set({left:(canvas.width - shape.getScaledWidth()) / 2, top:(canvas.height - shape.getScaledHeight()) / 2});
    canvas.add(shape);
    canvas.setActiveObject(shape);
    canvas.requestRenderAll();
    updateAnnotationButtons();
  }

  function imageSourceFor(step) {
    if (pendingFiles.has(step.uid)) return previewUrl(step.uid, pendingFiles.get(step.uid));
    return step.image_path ? `/uploads/${step.image_path}` : "";
  }

  async function openAnnotationEditor(sequenceIndex) {
    const step = state.sequences[sequenceIndex];
    const source = imageSourceFor(step);
    if (!source) return showErrors([`El paso ${sequenceIndex + 1} todavía no tiene una imagen para editar.`]);
    if (!window.fabric) return showErrors(["No se pudo iniciar el editor de fotografías. Reemplazá todos los archivos de la actualización."]);

    const modal = $("#annotation-modal");
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    $("#annotation-title").textContent = `Señaladores del paso ${sequenceIndex + 1}`;
    $("#annotation-loading").classList.remove("hidden");
    $("#annotation-stage").classList.add("hidden");
    $("#annotation-apply").disabled = true;
    const loadToken = ++annotationLoadToken;

    try {
      const image = await fabric.FabricImage.fromURL(source);
      if (loadToken !== annotationLoadToken) return;
      const sourceWidth = Math.max(1, +image.width || 1);
      const sourceHeight = Math.max(1, +image.height || 1);
      const outputScale = Math.min(1, 2000 / Math.max(sourceWidth, sourceHeight));
      const outputWidth = Math.max(1, Math.round(sourceWidth * outputScale));
      const outputHeight = Math.max(1, Math.round(sourceHeight * outputScale));
      const availableWidth = Math.max(300, Math.min(1040, window.innerWidth - 80));
      const availableHeight = Math.max(260, window.innerHeight - 310);
      const displayScale = Math.min(1, availableWidth / outputWidth, availableHeight / outputHeight);
      const displayWidth = Math.max(1, Math.round(outputWidth * displayScale));
      const displayHeight = Math.max(1, Math.round(outputHeight * displayScale));
      const canvas = new fabric.Canvas("annotation-canvas", {width:displayWidth, height:displayHeight, preserveObjectStacking:true, selection:true});
      image.set({left:0, top:0, originX:"left", originY:"top", scaleX:displayWidth / sourceWidth, scaleY:displayHeight / sourceHeight, selectable:false, evented:false});
      canvas.backgroundImage = image;
      annotationEditor = {canvas, step, sequenceIndex, source, outputMultiplier:outputWidth / displayWidth, history:[], historyIndex:-1, restoring:true, busy:false};
      canvas.on("object:added", rememberAnnotationState);
      canvas.on("object:modified", rememberAnnotationState);
      canvas.on("object:removed", rememberAnnotationState);
      canvas.on("selection:created", updateAnnotationButtons);
      canvas.on("selection:updated", updateAnnotationButtons);
      canvas.on("selection:cleared", updateAnnotationButtons);
      annotationEditor.restoring = false;
      rememberAnnotationState();
      canvas.requestRenderAll();
      $("#annotation-loading").classList.add("hidden");
      $("#annotation-stage").classList.remove("hidden");
      $("#annotation-apply").disabled = false;
      updateAnnotationButtons();
    } catch (error) {
      closeAnnotationEditor();
      showErrors(["No se pudo abrir la fotografía en el editor. Probá cargarla nuevamente como JPG o PNG."]);
    }
  }

  function closeAnnotationEditor() {
    annotationLoadToken += 1;
    if (annotationEditor?.canvas) annotationEditor.canvas.dispose();
    annotationEditor = null;
    $("#annotation-modal").classList.add("hidden");
    $("#annotation-stage").classList.add("hidden");
    document.body.style.overflow = "";
  }

  async function applyAnnotationEditor() {
    if (!annotationEditor || annotationEditor.busy) return;
    const editor = annotationEditor;
    editor.busy = true;
    $("#annotation-apply").disabled = true;
    $("#annotation-apply").textContent = "Aplicando…";
    updateAnnotationButtons();
    try {
      editor.canvas.discardActiveObject();
      editor.canvas.requestRenderAll();
      const blob = await editor.canvas.toBlob({format:"jpeg", quality:.92, multiplier:editor.outputMultiplier});
      if (!blob) throw new Error("No se pudo exportar la fotografía anotada.");
      const finalImage = new File([blob], `paso_${editor.sequenceIndex + 1}_anotada.jpg`, {type:"image/jpeg"});
      pendingFiles.set(editor.step.uid, finalImage);
      editor.step.upload_key = editor.step.uid;
      editor.step.annotation_data = {};
      editor.step.image_removed = false;
      closeAnnotationEditor();
      markDirty();
      renderSequences();
    } catch (error) {
      editor.busy = false;
      $("#annotation-apply").disabled = false;
      showErrors([error.message || "No se pudo aplicar la edición a la fotografía."]);
      updateAnnotationButtons();
    } finally {
      $("#annotation-apply").textContent = "Aplicar señaladores";
    }
  }

  function renderControls() {
    const root = $("#controls-list");
    if (!root) return;
    if (!state.controls.length) {
      root.innerHTML = `<div class="empty"><h3>Sin controles cargados</h3><p>Esta sección puede quedar vacía.</p></div>`;
      return;
    }
    const stepOptions = state.sequences.map((s, i) => option(i + 1, null, `Paso ${i + 1}`)).join("");
    root.innerHTML = state.controls.map((control, i) => `
      <div class="repeat-item inline-grid" data-control="${i}">
        <label><span>Paso *</span><select data-field="sequence_number">${state.sequences.map((s,n)=>option(n+1,control.sequence_number,`Paso ${n+1}`)).join("") || stepOptions}</select></label>
        <label><span>Característica *</span><input data-field="characteristic" value="${escapeHtml(control.characteristic)}"></label>
        <label><span>Medición</span><input value="Visual" disabled></label>
        <label><span>Muestreo</span><input value="100%" disabled></label>
        <label><span>Registro *</span><select data-field="record"><option value="">Seleccionar</option>${option("N/A", control.record)}${option("Tick en cordón", control.record)}</select></label>
        <button class="icon-button" type="button" data-remove="control">Eliminar</button>
      </div>`).join("");
  }

  function renderImportant() {
    const pages = Math.max(1, Math.ceil(state.sequences.length / 5));
    const root = $("#important-list");
    root.innerHTML = state.important.length ? state.important.map((item, i) => `
      <div class="repeat-item inline-grid" data-important="${i}">
        <label><span>Hoja</span><select data-field="page">${Array.from({length:pages},(_,n)=>option(n+1,item.page,`Hoja ${n+1}`)).join("")}</select></label>
        <label style="grid-column:span 4"><span>Texto</span><input data-field="text" value="${escapeHtml(item.text)}"></label>
        <button class="icon-button" type="button" data-remove="important">Eliminar</button>
      </div>`).join("") : `<p class="subtle">Sin observaciones IMPORTANTES.</p>`;
  }

  function renderRevisions() {
    const root = $("#revisions-list");
    root.innerHTML = state.revisions.length ? state.revisions.map((item, i) => `
      <div class="repeat-item inline-grid" data-revision="${i}">
        <label><span>Fecha</span><input type="date" data-field="date" value="${escapeHtml(item.date)}"></label>
        <label><span>LC</span><input data-field="lc" value="${escapeHtml(item.lc)}"></label>
        <label style="grid-column:span 2"><span>Modificación</span><input data-field="modification" value="${escapeHtml(item.modification)}"></label>
        <label><span>Realizó</span><input data-field="performed_by" value="${escapeHtml(item.performed_by)}"></label>
        <button class="icon-button" type="button" data-remove="revision">Eliminar</button>
      </div>`).join("") : `<p class="subtle">Sin historial de revisiones.</p>`;
  }

  function renderAll() { renderDocuments(); renderSequences(); renderImportant(); renderRevisions(); }

  function syncGeneral() {
    $$('[name]', $("#instruction-form")).forEach(input => {
      if (!input.disabled) state.general[input.name] = input.value;
    });
    state.general.model = "ESTÁNDAR";
  }

  function markDirty() { $("#save-state").textContent = "Cambios sin guardar"; }

  document.addEventListener("input", e => {
    if (!e.target.closest("#instruction-form")) return;
    markDirty();
    if (e.target.name === "station") updateAutomaticDocument();
    const seq = e.target.closest("[data-sequence]");
    if (seq && e.target.dataset.field) state.sequences[+seq.dataset.sequence][e.target.dataset.field] = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    const control = e.target.closest("[data-control]");
    if (control && e.target.dataset.field) state.controls[+control.dataset.control][e.target.dataset.field] = e.target.dataset.field === "sequence_number" ? +e.target.value : e.target.value;
    const doc = e.target.closest("[data-document]");
    if (doc && e.target.dataset.field) state.documents[+doc.dataset.document] = e.target.value;
    const imp = e.target.closest("[data-important]");
    if (imp && e.target.dataset.field) state.important[+imp.dataset.important][e.target.dataset.field] = e.target.dataset.field === "page" ? +e.target.value : e.target.value;
    const rev = e.target.closest("[data-revision]");
    if (rev && e.target.dataset.field) state.revisions[+rev.dataset.revision][e.target.dataset.field] = e.target.value;
  });

  document.addEventListener("change", e => {
    const item = e.target.closest("[data-sequence]");
    if (!item || !e.target.matches("[data-image-input]")) return;
    const step = state.sequences[+item.dataset.sequence];
    const file = e.target.files[0];
    if (file) {
      pendingFiles.set(step.uid, file);
      step.upload_key = step.uid;
      step.annotation_data = {};
      step.image_removed = false;
      markDirty();
      renderSequences();
    }
  });

  document.addEventListener("click", e => {
    const tab = e.target.closest("[data-tab]");
    if (tab) {
      $$(".tab").forEach(x => x.classList.toggle("active", x === tab));
      $$(".tab-panel").forEach(x => x.classList.toggle("active", x.dataset.panel === tab.dataset.tab));
      return;
    }
    const add = e.target.closest("[data-add]");
    if (add) {
      const type = add.dataset.add;
      if (type === "document") { state.documents.push(""); renderDocuments(); }
      if (type === "sequence") { state.sequences.push({uid:uid(),sequence:"",visual_summary:"",key_point:"",reason:"",image_path:"",annotation_data:{},safety_symbol:false,quality_symbol:false,triangle_s_number:""}); renderSequences(); renderImportant(); }
      if (type === "control") {
        if (!state.sequences.length) return showErrors(["Primero agregá al menos una secuencia."]);
        state.controls.push({sequence_number:1,characteristic:"",measurement:"Visual",sampling:"100%",record:""}); renderControls();
      }
      if (type === "important") { state.important.push({page:1,text:""}); renderImportant(); }
      if (type === "revision") { if(state.revisions.length >= 3) return showErrors(["La plantilla admite hasta tres revisiones."]); state.revisions.push({date:"",lc:"",modification:"",performed_by:""}); renderRevisions(); }
      markDirty(); return;
    }
    const remove = e.target.closest("[data-remove]");
    if (remove) {
      const type = remove.dataset.remove;
      const owner = remove.closest(`[data-${type}]`);
      const index = +owner.dataset[type];
      if (type === "sequence") { const step=state.sequences[index]; pendingFiles.delete(step.uid); state.sequences.splice(index,1); state.controls=state.controls.filter(c=>c.sequence_number!==index+1).map(c=>({...c,sequence_number:c.sequence_number>index+1?c.sequence_number-1:c.sequence_number})); renderSequences(); renderImportant(); }
      if (type === "document") { state.documents.splice(index,1); renderDocuments(); }
      if (type === "control") { state.controls.splice(index,1); renderControls(); }
      if (type === "important") { state.important.splice(index,1); renderImportant(); }
      if (type === "revision") { state.revisions.splice(index,1); renderRevisions(); }
      markDirty(); return;
    }
    const move = e.target.closest("[data-move]");
    if (move) {
      const index = +move.closest("[data-sequence]").dataset.sequence;
      const target = move.dataset.move === "up" ? index - 1 : index + 1;
      if (target >= 0 && target < state.sequences.length) [state.sequences[index],state.sequences[target]]=[state.sequences[target],state.sequences[index]];
      renderSequences(); renderImportant(); markDirty(); return;
    }
    const editImage = e.target.closest("[data-edit-image]");
    if (editImage) {
      const index = +editImage.closest("[data-sequence]").dataset.sequence;
      openAnnotationEditor(index);
      return;
    }
    const removeImage = e.target.closest("[data-remove-image]");
    if (removeImage) {
      const step = state.sequences[+removeImage.closest("[data-sequence]").dataset.sequence];
      pendingFiles.delete(step.uid); step.upload_key=""; step.image_removed=true; step.image_path=""; step.annotation_data={}; renderSequences(); markDirty();
    }
  });

  $$('[data-annotation-add]').forEach(button => button.addEventListener("click", () => addAnnotationShape(button.dataset.annotationAdd)));
  $("#annotation-close").addEventListener("click", closeAnnotationEditor);
  $("#annotation-cancel").addEventListener("click", closeAnnotationEditor);
  $("#annotation-apply").addEventListener("click", applyAnnotationEditor);
  $("#annotation-delete").addEventListener("click", () => {
    if (!annotationEditor) return;
    const selected = annotationEditor.canvas.getActiveObjects();
    annotationEditor.canvas.discardActiveObject();
    selected.forEach(object => annotationEditor.canvas.remove(object));
    annotationEditor.canvas.requestRenderAll();
    updateAnnotationButtons();
  });
  $("#annotation-undo").addEventListener("click", async () => {
    if (!annotationEditor || annotationEditor.historyIndex <= 0) return;
    annotationEditor.historyIndex -= 1;
    await restoreAnnotationState(annotationEditor.history[annotationEditor.historyIndex]);
  });
  $("#annotation-redo").addEventListener("click", async () => {
    if (!annotationEditor || annotationEditor.historyIndex >= annotationEditor.history.length - 1) return;
    annotationEditor.historyIndex += 1;
    await restoreAnnotationState(annotationEditor.history[annotationEditor.historyIndex]);
  });

  function updateActiveAnnotationStyle() {
    if (!annotationEditor) return;
    const color = $("#annotation-color").value;
    const width = +$("#annotation-width").value;
    annotationEditor.canvas.getActiveObjects().forEach(object => object.set({stroke:color, strokeWidth:width}));
    annotationEditor.canvas.requestRenderAll();
    rememberAnnotationState();
  }

  $("#annotation-width").addEventListener("input", e => { $("#annotation-width-value").value = e.target.value; });
  $("#annotation-width").addEventListener("change", updateActiveAnnotationStyle);
  $("#annotation-color").addEventListener("change", updateActiveAnnotationStyle);
  document.addEventListener("keydown", async e => {
    if (!annotationEditor) return;
    if (e.key === "Escape") { e.preventDefault(); closeAnnotationEditor(); return; }
    if ((e.key === "Delete" || e.key === "Backspace") && annotationEditor.canvas.getActiveObjects().length) {
      e.preventDefault(); $("#annotation-delete").click(); return;
    }
    if (e.ctrlKey && e.key.toLowerCase() === "z") { e.preventDefault(); $(e.shiftKey ? "#annotation-redo" : "#annotation-undo").click(); }
    if (e.ctrlKey && e.key.toLowerCase() === "y") { e.preventDefault(); $("#annotation-redo").click(); }
  });

  function showErrors(errors) {
    const box = $("#error-box");
    box.innerHTML = `<strong>Revisá lo siguiente:</strong><ul>${errors.map(e=>`<li>${escapeHtml(e)}</li>`).join("")}</ul>`;
    box.classList.remove("hidden"); window.scrollTo({top:0,behavior:"smooth"});
  }

  $("#instruction-form").addEventListener("submit", async e => {
    e.preventDefault(); syncGeneral();
    state.sequences.forEach((s,i)=>s.number=i+1);
    const button=$("#save-button"); button.disabled=true; button.textContent="Guardando…"; $("#error-box").classList.add("hidden");
    const formData=new FormData(); formData.append("payload",JSON.stringify(state));
    pendingFiles.forEach((file,key)=>formData.append(`image_${key}`,file));
    try {
      const endpoint=window.INSTRUCTION_ID ? `/api/instrucciones/${window.INSTRUCTION_ID}` : "/api/instrucciones";
      const response=await fetch(endpoint,{method:"POST",body:formData});
      const result=await response.json();
      if(!response.ok || !result.ok) throw result;
      $("#save-state").textContent="Guardado"; window.location=result.redirect;
    } catch(error) { showErrors(error.errors || ["No se pudo guardar. Verificá que la aplicación siga abierta."]); button.disabled=false; button.textContent="Guardar instrucción"; }
  });

  loadGeneral(); renderAll();
})();
