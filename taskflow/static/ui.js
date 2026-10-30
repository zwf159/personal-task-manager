'use strict';
let panelSequence = 0;
const UI = {
  confirm(title, message, action) {
    const panel = UI.panel(title);
    panel.body.append(element('p', '', message), UI.button('取消', () => panel.dialog.close()),
      UI.button('确认', async () => {await action(); panel.dialog.close();}));
  },
  button(label, action, className = 'secondary') {
    const button = element('button', className, label);
    button.type = 'button';
    button.onclick = async () => {
      button.disabled = true;
      try {await action();} catch (error) {toast(error.message);} finally {button.disabled = false;}
    };
    return button;
  },
  panel(title) {
    const previousFocus = document.activeElement;
    const dialog = element('dialog', 'feature-panel');
    const header = element('div', 'dialog-heading');
    const heading = element('h2', '', title);
    heading.id = `feature-panel-${++panelSequence}`;
    dialog.setAttribute('aria-labelledby', heading.id);
    header.append(heading, UI.button('关闭', () => dialog.close()));
    const body = element('div', 'panel-body');
    dialog.append(header, body);
    document.body.append(dialog);
    dialog.addEventListener('close', () => {dialog.remove(); if (previousFocus?.isConnected) previousFocus.focus();}, {once: true});
    dialog.showModal();
    return {dialog, body};
  },
  section(root, title) {
    const section = element('section', 'detail-section');
    section.append(element('h3', '', title));
    root.append(section);
    return section;
  },
  line(root, label, controls = []) {
    const line = element('div', 'detail-line');
    line.append(element('span', 'line-content', label), ...controls);
    root.append(line);
    return line;
  },
  form(fields, submit, label = '添加') {
    const form = element('form', 'inline-form');
    for (const field of fields) {
      const wrapper = element('label', '', field.label);
      const input = element(field.options ? 'select' : field.type === 'textarea' ? 'textarea' : 'input');
      input.name = field.name;
      input.setAttribute('aria-label', field.label);
      if (field.options) for (const [value, title] of field.options) input.add(new Option(title, value));
      else if (field.type !== 'textarea') input.type = field.type || 'text';
      input.required = field.required !== false;
      if (field.maxLength) input.maxLength = field.maxLength;
      if (field.min !== undefined) input.min = field.min;
      if (field.max !== undefined) input.max = field.max;
      if (field.value !== undefined) input.value = field.value;
      wrapper.append(input);
      form.append(wrapper);
    }
    const button = element('button', 'primary', label);
    const errorMessage = element('p', 'form-error inline-error');
    errorMessage.setAttribute('role', 'alert');
    button.type = 'submit';
    form.append(button, errorMessage);
    form.onsubmit = async event => {
      event.preventDefault();
      if (button.disabled) return;
      button.disabled = true;
      errorMessage.textContent = '';
      try {await submit(Object.fromEntries(new FormData(form)));}
      catch (error) {errorMessage.textContent = error.message; toast(error.message);}
      finally {button.disabled = false;}
    };
    return form;
  }
};
