/**
 * ChemELN Rich Text Editor — contenteditable-based editor with toolbar.
 * Supports: headings, bold/italic/underline, lists, tables, images, code blocks.
 */
class RichEditor {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.onChange = options.onChange || (() => {});
    this.build();
  }

  build() {
    this.container.innerHTML = '';

    // Toolbar
    const toolbar = document.createElement('div');
    toolbar.className = 'editor-toolbar';
    toolbar.innerHTML = `
      <button class="editor-btn" data-cmd="formatBlock" data-val="H2" title="标题">H2</button>
      <button class="editor-btn" data-cmd="formatBlock" data-val="H3" title="小标题">H3</button>
      <button class="editor-btn" data-cmd="formatBlock" data-val="P" title="正文">¶</button>
      <div class="editor-divider"></div>
      <button class="editor-btn" data-cmd="bold" title="粗体"><b>B</b></button>
      <button class="editor-btn" data-cmd="italic" title="斜体"><i>I</i></button>
      <button class="editor-btn" data-cmd="underline" title="下划线"><u>U</u></button>
      <button class="editor-btn" data-cmd="strikeThrough" title="删除线"><s>S</s></button>
      <div class="editor-divider"></div>
      <button class="editor-btn" data-cmd="insertUnorderedList" title="无序列表">•</button>
      <button class="editor-btn" data-cmd="insertOrderedList" title="有序列表">1.</button>
      <div class="editor-divider"></div>
      <button class="editor-btn" data-action="insertTable" title="插入表格">⊞</button>
      <button class="editor-btn" data-action="insertImage" title="插入图片">🖼</button>
      <button class="editor-btn" data-action="insertPdf" title="插入PDF">PDF</button>
      <button class="editor-btn" data-action="insertCode" title="代码块">{ }</button>
      <button class="editor-btn" data-action="insertHR" title="分割线">―</button>
      <div class="editor-divider"></div>
      <button class="editor-btn" data-cmd="undo" title="撤销">↶</button>
      <button class="editor-btn" data-cmd="redo" title="重做">↷</button>
      <button class="editor-btn" data-action="clearFormat" title="清除格式" style="margin-left:auto">⌫</button>
    `;
    this.container.appendChild(toolbar);

    // Content area
    this.content = document.createElement('div');
    this.content.className = 'editor-content';
    this.content.setAttribute('contenteditable', 'true');
    this.content.setAttribute('data-placeholder', '在此输入实验内容... 支持标题、列表、表格、图片、PDF、代码块');
    this.container.appendChild(this.content);

    // Hidden file input for PDF insertion
    this.pdfInput = document.createElement('input');
    this.pdfInput.type = 'file';
    this.pdfInput.accept = '.pdf,application/pdf';
    this.pdfInput.style.display = 'none';
    this.pdfInput.addEventListener('change', () => {
      const file = this.pdfInput.files && this.pdfInput.files[0];
      if (file && this.options.onInsertPdf) {
        this.options.onInsertPdf(file);
      }
      this.pdfInput.value = ''; // allow re-selecting the same file
    });
    this.container.appendChild(this.pdfInput);

    // Bind toolbar
    toolbar.querySelectorAll('.editor-btn').forEach(btn => {
      btn.addEventListener('mousedown', e => e.preventDefault()); // prevent losing focus
      btn.addEventListener('click', () => this.handleToolbar(btn));
    });

    // Content events
    this.content.addEventListener('input', () => {
      this.onChange(this.content.innerHTML);
    });

    // Image paste
    this.content.addEventListener('paste', (e) => this.handlePaste(e));

    // Keyboard shortcuts
    this.content.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (this.options.onSave) this.options.onSave();
      }
    });
  }

  handleToolbar(btn) {
    const cmd = btn.dataset.cmd;
    const action = btn.dataset.action;
    const val = btn.dataset.val;

    if (cmd) {
      document.execCommand(cmd, false, val);
      this.content.focus();
      this.onChange(this.content.innerHTML);
    } else if (action) {
      this.handleAction(action);
    }
  }

  handleAction(action) {
    switch (action) {
      case 'insertTable':
        const rows = prompt('行数:', '3');
        const cols = prompt('列数:', '3');
        if (rows && cols) {
          let html = '<table><tbody>';
          for (let i = 0; i < parseInt(rows); i++) {
            html += '<tr>';
            for (let j = 0; j < parseInt(cols); j++) {
              html += i === 0 ? '<th>表头</th>' : '<td>&nbsp;</td>';
            }
            html += '</tr>';
          }
          html += '</tbody></table><p></p>';
          document.execCommand('insertHTML', false, html);
        }
        break;
      case 'insertImage':
        const url = prompt('图片URL或本地路径:', '');
        if (url) {
          document.execCommand('insertImage', false, url);
        }
        break;
      case 'insertPdf':
        if (this.options.onInsertPdf) {
          this.pdfInput.click();
        } else {
          alert('当前未配置 PDF 上传，请先保存实验。');
        }
        break;
      case 'insertCode':
        document.execCommand('insertHTML', false,
          '<pre><code>code here</code></pre><p></p>');
        break;
      case 'insertHR':
        document.execCommand('insertHorizontalRule');
        break;
      case 'clearFormat':
        document.execCommand('removeFormat');
        break;
    }
    this.content.focus();
    this.onChange(this.content.innerHTML);
  }

  handlePaste(e) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const blob = item.getAsFile();
        const reader = new FileReader();
        reader.onload = (ev) => {
          document.execCommand('insertImage', false, ev.target.result);
          this.onChange(this.content.innerHTML);
        };
        reader.readAsDataURL(blob);
        return;
      }
    }
    // Check for mol block paste (from ChemDraw)
    const text = e.clipboardData?.getData('text/plain') || '';
    if (text.includes('M  END') || text.startsWith('V2000') || text.startsWith('V3000')) {
      // This looks like a mol block — could be from ChemDraw
      // Let it paste normally, the structure editor will handle it separately
    }
  }

  setHTML(html) {
    this.content.innerHTML = html || '';
  }

  getHTML() {
    return this.content.innerHTML;
  }

  insertHTML(html) {
    document.execCommand('insertHTML', false, html);
    this.onChange(this.content.innerHTML);
  }

  insertImage(dataUrl) {
    document.execCommand('insertImage', false, dataUrl);
    this.onChange(this.content.innerHTML);
  }

  // Insert a PDF icon card at the cursor position (click to open).
  // attId = attachment id, used by the delete button to remove the file too.
  insertPdf(url, name, attId) {
    const safeName = (name || 'document.pdf').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const att = attId != null ? ` data-att-id="${attId}"` : '';
    const delBtn = attId != null
      ? `<button class="pdf-embed-del" type="button" onclick="App.deletePdfEmbed(this)">删除</button>`
      : '';
    const html = `
      <div class="pdf-embed" contenteditable="false" data-pdf="${url}"${att}>
        <div class="pdf-embed-icon">PDF</div>
        <div class="pdf-embed-info">
          <span class="pdf-name">${safeName}</span>
          <span class="pdf-hint">点击打开 PDF 文件</span>
        </div>
        <a class="pdf-embed-open" href="${url}" target="_blank" rel="noopener">打开</a>
        ${delBtn}
      </div><p></p>`;
    document.execCommand('insertHTML', false, html);
    this.content.focus();
    this.onChange(this.content.innerHTML);
  }
}
