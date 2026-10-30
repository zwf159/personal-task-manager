'use strict';
const Workspace = {
  entries: [],
  register(name, title, description, open) {this.entries.push({name, title, description, open});},
  async open() {
    const panel = UI.panel('个人工作台');
    const grid = element('div', 'extension-grid');
    for (const entry of this.entries) {
      const card = element('article', 'extension-card');
      card.append(element('h3', '', entry.title), element('p', '', entry.description),
        UI.button('打开' + entry.title, async () => {panel.dialog.close(); await entry.open();}));
      grid.append(card);
    }
    panel.body.append(grid);
  },
  async changed() {await refresh();},
};
$('#tools').append(UI.button('个人工作台', () => Workspace.open()));
for (const name of ['goals', 'habits', 'inbox', 'notes', 'planner', 'reviews', 'rules']) {
  const style = document.createElement('link'); style.rel = 'stylesheet'; style.href = `/extensions/${name}.css`; document.head.append(style);
  const script = document.createElement('script'); script.src = `/extensions/${name}.js`; script.async = false;
  script.onerror = () => toast(`工作台模块加载失败：${name}`);
  document.head.append(script);
}
