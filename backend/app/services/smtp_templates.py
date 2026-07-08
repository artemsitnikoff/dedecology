"""HTML-шаблоны писем «ЭкоПульс».

`_email_shell` — общий каркас (хедер с брендом + подпись + футер), применяется ко
ВСЕМ письмам ради единообразия. `render_simple_email` — универсальное письмо
(заголовок + произвольный HTML-контент, формируемый кодом).

Вёрстка table-based + inline-стили (email-клиенты не поддерживают внешний CSS/flex).
Пользовательские значения экранируются (html.escape). Письмо в UTF-8, кириллица — как есть.
Бренд: эко-зелёный акцент, эмодзи 💚, имя «ЭкоПульс».
"""

import html as _html

# Эко-зелёный акцент бренда (совпадает по духу с фронтовым --de-brand).
BRAND_GREEN = "#1F9D57"
BRAND_GREEN_DARK = "#177544"
INK = "#0F1B12"
MUTED = "#5B6B60"
BG = "#EAF2EC"


def _email_shell(content_html: str, preheader: str = "") -> str:
    """Оборачивает контент письма в общий хедер (бренд) + подпись + футер."""
    pre = _html.escape(preheader)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta http-equiv="X-UA-Compatible" content="IE=edge"/>
</head>
<body style="margin:0;padding:0;width:100%;background:{BG};-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;height:0;width:0;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG};">
  <tr><td align="center" style="padding:40px 16px;">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:560px;max-width:560px;background:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 12px 32px rgba(15,27,18,.10);">
      <tr><td style="padding:28px 40px 26px;border-bottom:1px solid {BG};">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="width:32px;height:32px;border-radius:8px;background:{BRAND_GREEN};background-image:linear-gradient(135deg,{BRAND_GREEN} 0%,{BRAND_GREEN_DARK} 100%);text-align:center;vertical-align:middle;font-size:18px;line-height:32px;">💚</td>
          <td style="padding-left:10px;vertical-align:middle;">
            <span style="font-family:'Inter',Arial,sans-serif;font-size:16px;font-weight:700;letter-spacing:-0.01em;color:{INK};">ЭкоПульс</span>
          </td>
        </tr></table>
      </td></tr>
      {content_html}
      <tr><td style="padding:28px 40px 0;"><div style="border-top:1px solid {BG};height:1px;line-height:1px;font-size:0;">&nbsp;</div></td></tr>
      <tr><td style="padding:22px 40px 32px;">
        <p style="margin:0 0 3px;font-family:'Inter',Arial,sans-serif;font-size:14px;line-height:1.5;color:{MUTED};">С уважением,</p>
        <p style="margin:0;font-family:'Inter',Arial,sans-serif;font-size:14px;font-weight:600;line-height:1.5;color:{INK};">Команда ЭкоПульс</p>
      </td></tr>
    </table>
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:560px;max-width:560px;">
      <tr><td style="padding:22px 40px 8px;text-align:center;">
        <p style="margin:0;font-family:'Inter',Arial,sans-serif;font-size:12px;line-height:1.6;color:{MUTED};">Это письмо отправлено автоматически. Если вы не ожидали его, просто проигнорируйте.</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _heading(text: str) -> str:
    return (
        "<h1 style=\"margin:0 0 18px;font-family:'Inter',Arial,sans-serif;font-size:22px;"
        f"font-weight:600;line-height:1.3;letter-spacing:-0.01em;color:{INK};\">"
        f"{_html.escape(text)}</h1>"
    )


def render_simple_email(heading: str, body_html: str, preheader: str = "") -> str:
    """Универсальное письмо: заголовок + произвольный HTML-контент кода.

    body_html — внутренний HTML (формируется кодом, НЕ пользовательский ввод);
    heading экранируется. Каркас/бренд — общий (_email_shell).
    """
    content = f"""
      <tr><td style="padding:34px 40px 8px;">
        {_heading(heading)}
        <div style="font-family:'Inter',Arial,sans-serif;font-size:15px;line-height:1.6;color:{MUTED};">{body_html}</div>
      </td></tr>
    """
    return _email_shell(content, preheader=preheader or heading)
