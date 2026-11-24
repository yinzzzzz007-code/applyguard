import type {ResumeBlock} from './generate'

const specials: Record<string,string> = {
  '\\':'\\textbackslash{}', '{':'\\{', '}':'\\}', '%':'\\%', '&':'\\&', '$':'\\$', '#':'\\#',
  '_':'\\_', '~':'\\textasciitilde{}', '^':'\\textasciicircum{}',
}

function escapeText(value:string) {
  return value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'')
    .replace(/[\\{}%&$#_~^]/g, char => specials[char]).replace(/\r\n?|\n/g,'\\par\n')
}

export function buildLatex(blocks: ResumeBlock[]): string {
  const lines = [
    '% !TeX program = xelatex',
    '% UTF-8 | Compile with XeLaTeX (TeX Live or Overleaf).',
    '\\documentclass[11pt,a4paper]{article}',
    '\\usepackage{xeCJK}',
    '\\IfFileExists{FandolSong-Regular.otf}{\\setCJKmainfont[BoldFont=FandolSong-Bold.otf]{FandolSong-Regular.otf}}{%',
    '  \\IfFontExistsTF{Microsoft YaHei}{\\setCJKmainfont{Microsoft YaHei}}{%',
    '    \\IfFontExistsTF{PingFang SC}{\\setCJKmainfont{PingFang SC}}{\\setCJKmainfont{Noto Serif CJK SC}}}}',
    '\\setlength{\\textwidth}{\\dimexpr\\paperwidth-40mm\\relax}',
    '\\setlength{\\oddsidemargin}{\\dimexpr20mm-1in\\relax}',
    '\\setlength{\\topmargin}{\\dimexpr20mm-1in\\relax}',
    '\\setlength{\\headheight}{0pt}\\setlength{\\headsep}{0pt}',
    '\\setlength{\\textheight}{\\dimexpr\\paperheight-40mm\\relax}',
    '\\pagestyle{empty}', '\\setlength{\\parindent}{0pt}', '\\setlength{\\parskip}{4pt}',
    '\\emergencystretch=2em', '\\begin{document}',
  ]
  let inList = false
  for (const {kind,text} of blocks) {
    if (!text.trim()) continue
    if (inList && kind !== 'bullet') {lines.push('\\end{itemize}'); inList = false}
    const value = escapeText(text)
    if (kind === 'bullet') {
      if (!inList) {lines.push('\\begin{itemize}'); inList = true}
      lines.push('\\item '+value)
    } else if (kind === 'heading') lines.push('', '\\section*{'+value+'}')
    else if (kind === 'name') lines.push('{\\LARGE\\bfseries '+value+'\\par}')
    else lines.push(value+'\\par')
  }
  if (inList) lines.push('\\end{itemize}')
  return [...lines,'\\end{document}',''].join('\n')
}

export function downloadFile(text:string, filename:string, mime:string) {
  const url = URL.createObjectURL(new Blob([text],{type:mime}))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url),1000)
}
