# -*- coding: utf-8 -*-
import html


def render_bid_board_email(
    headline,
    intro_lines,
    detail_pairs,
    *,
    tagline=None,
    cta_label=None,
    cta_url=None,
    footer_hint=None,
):
    """Return a table-based HTML body for transactional Bid Board emails (client-safe)."""
    esc = html.escape

    def p_line(text):
        return f'<p style="margin:0 0 14px 0;">{esc(text)}</p>'

    intro_html = "".join(p_line(line) for line in intro_lines if line)
    rows_html = []
    for label, value in detail_pairs:
        label_s = esc(str(label))
        value_s = esc(str(value)) if value is not None else ""
        rows_html.append(
            f'<tr>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #e8edf2;font:13px/1.5 Arial,Helvetica,sans-serif;'
            f'color:#64748b;width:38%;vertical-align:top;">{label_s}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #e8edf2;font:600 14px/1.5 Arial,Helvetica,sans-serif;'
            f'color:#0f172a;vertical-align:top;">{value_s}</td>'
            f"</tr>"
        )
    details_block = "".join(rows_html)
    tagline_html = ""
    if tagline:
        tagline_html = (
            f'<p style="margin:10px 0 0 0;font:400 15px/1.5 Arial,Helvetica,sans-serif;color:rgba(255,255,255,.9);">'
            f"{esc(tagline)}</p>"
        )

    cta_html = ""
    if cta_label and cta_url:
        safe_url = esc(str(cta_url), quote=True)
        cta_html = f"""
<tr>
  <td style="padding:8px 28px 28px;">
    <a href="{safe_url}" style="display:inline-block;padding:12px 22px;background:#0f2841;color:#ffffff !important;
      text-decoration:none;font:600 14px Arial,Helvetica,sans-serif;border-radius:6px;letter-spacing:0.02em;">
      {esc(cta_label)}
    </a>
  </td>
</tr>"""
    elif cta_label:
        cta_html = ""

    footer = footer_hint or (
        "This message was sent automatically by Berkeley UAE Bid Board. "
        "If you have questions, contact your bid manager or project lead."
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width"/></head>
<body style="margin:0;padding:0;background:#e8edf2;-webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e8edf2;">
  <tr>
    <td align="center" style="padding:28px 16px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
        style="max-width:600px;width:100%;background:#ffffff;border-radius:10px;overflow:hidden;
        box-shadow:0 4px 24px rgba(15,40,65,0.08);border:1px solid #d6dee6;">
        <tr>
          <td bgcolor="#0f2841" style="background:linear-gradient(135deg,#0f2841 0%,#1a4a6e 100%);padding:26px 28px 22px;
            border-bottom:4px solid #c5a059;">
            <div style="font:600 11px/1.4 Arial,Helvetica,sans-serif;color:rgba(255,255,255,0.55);
              letter-spacing:0.14em;text-transform:uppercase;">Berkeley UAE — Bid Board</div>
            <div style="font:700 24px/1.25 Arial,Helvetica,sans-serif;color:#ffffff;margin-top:8px;letter-spacing:-0.02em;">
              {esc(headline)}
            </div>
            {tagline_html}
          </td>
        </tr>
        <tr>
          <td style="padding:26px 28px 8px;font:15px/1.65 Arial,Helvetica,sans-serif;color:#334155;">
            {intro_html}
          </td>
        </tr>
        <tr>
          <td style="padding:4px 28px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
              style="border-collapse:separate;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;background:#f8fafc;">
              {details_block}
            </table>
          </td>
        </tr>
        {cta_html}
        <tr>
          <td style="padding:0 28px 26px;font:12px/1.55 Arial,Helvetica,sans-serif;color:#94a3b8;">
            {esc(footer)}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
""".strip()
