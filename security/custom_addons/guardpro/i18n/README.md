# GuardPro - Internationalization (i18n)

This directory contains translation files for the GuardPro module.

## Available Languages

- **English (en_US)** - Default language (built-in)
- **Arabic (ar)** - Arabic translation
- **Spanish (es)** - Spanish translation
- **French (fr)** - French translation

## How to Export Translations

To export translatable strings from the module:

```bash
cd /home/ranjith/odoo
./odoo-18.0/odoo-bin -c odoo.conf \
  --stop-after-init \
  --i18n-export=/home/ranjith/odoo/custom_addons/guardpro/i18n/guardpro.pot \
  --modules=guardpro \
  --database=YOUR_DATABASE
```

## How to Create Language Files

### Method 1: Copy from Template
```bash
cd /home/ranjith/odoo/custom_addons/guardpro/i18n/
cp guardpro.pot ar.po
cp guardpro.pot es.po
cp guardpro.pot fr.po
```

Then edit each file to add translations.

### Method 2: Use POEdit
1. Install POEdit: `sudo apt install poedit`
2. Open guardpro.pot
3. Create new translation from template
4. Save as language code (ar.po, es.po, fr.po)

## How to Load Translations

To load a translation into Odoo:

```bash
cd /home/ranjith/odoo
./odoo-18.0/odoo-bin -c odoo.conf \
  --i18n-import=/home/ranjith/odoo/custom_addons/guardpro/i18n/ar.po \
  -l ar \
  --database=YOUR_DATABASE \
  --stop-after-init
```

## How to Update Existing Translations

```bash
cd /home/ranjith/odoo
./odoo-18.0/odoo-bin -c odoo.conf \
  --i18n-overwrite \
  --i18n-import=/home/ranjith/odoo/custom_addons/guardpro/i18n/ar.po \
  -l ar \
  --database=YOUR_DATABASE \
  --stop-after-init
```

## Translation Status

| Language | Code | Status | Completion |
|----------|------|--------|------------|
| English | en_US | ✅ Complete | 100% (Default) |
| Arabic | ar | 🟡 Template Created | 0% |
| Spanish | es | 🟡 Template Created | 0% |
| French | fr | 🟡 Template Created | 0% |

## File Structure

```
i18n/
├── README.md           # This file
├── guardpro.pot        # Translation template (generated)
├── ar.po              # Arabic translations
├── es.po              # Spanish translations
└── fr.po              # French translations
```

## Translation Guidelines

### What to Translate
- ✅ Field labels and help text
- ✅ Selection field options
- ✅ Button labels
- ✅ Menu names
- ✅ Error messages and warnings
- ✅ Email templates
- ✅ Report templates
- ✅ User notifications

### What NOT to Translate
- ❌ Technical field names (model names, field names)
- ❌ XML IDs
- ❌ Python code (only strings in _() function)
- ❌ Database values (use separate data files)

### Translation Best Practices

1. **Consistency**: Use same translation for same term throughout
2. **Context**: Consider context when translating (Guard vs. Security Guard)
3. **Length**: Keep translations similar length to avoid UI issues
4. **Formality**: Use appropriate formality level for business context
5. **Test**: Always test in Odoo UI after loading

### Common Terms Translation Reference

| English | Arabic | Spanish | French |
|---------|--------|---------|--------|
| Guard | حارس | Guardia | Gardien |
| Shift | مناوبة | Turno | Poste |
| Incident | حادثة | Incidente | Incident |
| Checkpoint | نقطة تفتيش | Punto de control | Point de contrôle |
| Tour | جولة | Ronda | Ronde |
| Site | موقع | Sitio | Site |
| Alert | تنبيه | Alerta | Alerte |
| Emergency | طوارئ | Emergencia | Urgence |

## Professional Translation Services

For production use, we recommend professional translation services:

1. **Gengo** - https://gengo.com
2. **Transifex** - https://www.transifex.com
3. **Crowdin** - https://crowdin.com
4. **Local Translation Agency** - For certified translations

## Testing Translations

1. Load translation using command above
2. Change user language:
   - Go to Settings > Users > Your User
   - Change Language field
   - Save and refresh browser
3. Verify all translations appear correctly
4. Check for:
   - Missing translations
   - Text overflow in UI
   - Proper RTL support (for Arabic)

## RTL (Right-to-Left) Support

For Arabic and other RTL languages:
- Odoo automatically handles RTL layout
- Test thoroughly in Arabic mode
- Check form layouts, tables, and reports
- Ensure numbers and dates display correctly

## Updating Translations

When you add new features or modify text:

1. Export new .pot file
2. Update existing .po files with new strings
3. Translate new strings
4. Reload translations into Odoo
5. Test in all languages

## Support

For translation issues:
- Check Odoo logs: `/var/log/odoo/odoo.log`
- Validate .po file syntax
- Ensure file encoding is UTF-8
- Verify language code is correct

---

**Last Updated:** October 11, 2025  
**Module Version:** 18.0.1.0.0  
**Status:** Templates Ready - Awaiting Professional Translation


