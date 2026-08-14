/**
 * Mobile incident wizard: type → category filtering, type-specific fields,
 * and detail-page section visibility.
 */
(function () {
    'use strict';

  var GP_TYPE_CATEGORY_CODES = {
    suspicious_person: ['SUSP', 'TRESP', 'DIST'],
    medical_emergency: ['MED', 'FIRE'],
    property_damage: ['SAFE', 'STRUCT', 'FLOOD', 'PWR_OUT', 'HVAC_FAIL'],
    community_violation: [
      'VAND', 'SHORT_LET', 'ILL_STAFF', 'MOVE_POL', 'SALE_POL',
      'ANIMAL', 'DMG_REC', 'DMG_COM', 'DMG_SPT', 'DMG_POOL', 'DMG_PLNT',
      'GARDEN', 'HOME_APP', 'EXT_MAJ', 'EXT_MIN', 'SIGNAGE', 'TERRACE',
      'PEST', 'GARAGE', 'RETAIL', 'ACS', 'ABSCS', 'MIS-COMMON', 'VOSSP', 'VSSP',
    ],
    parking_violation: [
      'LT_PARK', 'DBL_PARK', 'BLK_ACCESS', 'ILLEGAL_PARK', 'VIS_PARK',
      'WRONG_PARK', 'UNDESIG_PARK', 'UNAUTH_VEH', 'PAVEMENT_PARK',
      'DISABLED_PARK', 'FIRE_HYD_PARK', 'LOAD_ZONE', 'PED_CROSS',
      'OVERNIGHT_PARK', 'RETAIL_PARK', 'NO_PAY_EXIT', 'LOST_TICKET', 'ABND_VEH',
    ],
    security_breach: ['SEC', 'THEFT'],
    equipment_malfunction: ['EQUIP', 'EQ_HO', 'CCTV_HO'],
    other: [
      'OTHER', 'STMT', 'STATEMENT', 'FOUND', 'FOUND ITEM', 'RETURN', 'RETURN FORM',
      'VEH', 'WEATH', 'AUTH_VISIT',
    ],
  };

  var GP_TYPE_DEFAULT_CODE = {
    suspicious_person: 'SUSP',
    medical_emergency: 'MED',
    property_damage: 'SAFE',
    community_violation: 'VAND',
    parking_violation: 'ILLEGAL_PARK',
    security_breach: 'SEC',
    equipment_malfunction: 'EQUIP',
    other: 'OTHER',
  };

  var GP_STATEMENT_CODES = { STMT: 1, STATEMENT: 1 };
  var GP_FOUND_CODES = { FOUND: 1, 'FOUND ITEM': 1 };
  var GP_RETURN_CODES = { RETURN: 1, 'RETURN FORM': 1 };

  var GP_CODE_TO_TYPE = {};
  Object.keys(GP_TYPE_CATEGORY_CODES).forEach(function (type) {
    var codes = GP_TYPE_CATEGORY_CODES[type];
    if (!codes) return;
    codes.forEach(function (code) {
      GP_CODE_TO_TYPE[code] = type;
    });
  });

  var GP_DETAIL_SECTIONS = {
    suspicious_person: ['location', 'people', 'actions', 'emergency', 'photos'],
    medical_emergency: ['location', 'people', 'actions', 'emergency', 'injuries', 'photos'],
    property_damage: ['location', 'actions', 'property', 'photos'],
    community_violation: ['location', 'people', 'actions', 'property', 'photos'],
    parking_violation: ['location', 'people', 'actions', 'photos'],
    security_breach: ['location', 'people', 'actions', 'emergency', 'property', 'photos'],
    equipment_malfunction: ['location', 'actions', 'photos'],
    other: null,
  };

  var GP_WIZARD_TYPE_FIELDS = [
    'mobile-type-suspicious-fields',
    'mobile-type-medical-fields',
    'mobile-type-security-fields',
    'mobile-type-property-fields',
    'mobile-type-community-fields',
    'mobile-type-parking-fields',
    'mobile-type-equipment-fields',
  ];

  var GP_WIZARD_TYPE_MAP = {
    suspicious_person: 'mobile-type-suspicious-fields',
    medical_emergency: 'mobile-type-medical-fields',
    security_breach: 'mobile-type-security-fields',
    property_damage: 'mobile-type-property-fields',
    community_violation: 'mobile-type-community-fields',
    parking_violation: 'mobile-type-parking-fields',
    equipment_malfunction: 'mobile-type-equipment-fields',
  };

  var GP_TYPE_CATEGORY_NAME_HINTS = {
    suspicious_person: ['suspicious activity', 'suspicious', 'trespass', 'disturbance'],
    medical_emergency: ['medical emergency', 'medical', 'fire/smoke', 'fire'],
    property_damage: ['safety hazard', 'structural', 'flood', 'power outage', 'hvac'],
    community_violation: [
      'vandalism', 'community', 'violation', 'short term', 'animal', 'garden',
      'terrace', 'signage', 'retail', 'misuse', 'damage/misuse',
    ],
    parking_violation: [
      'parking', 'double park', 'illegal park', 'visitor park', 'long-term',
      'abandoned vehicle', 'hydrant', 'pavement', 'disabled parking',
    ],
    security_breach: ['security breach', 'theft', 'burglary'],
    equipment_malfunction: ['equipment malfunction', 'equipment handover', 'cctv handover', 'equipment'],
    other: ['other'],
  };

  function inferCodeFromCategoryName(name) {
    var n = (name || '').toLowerCase();
    if (n.indexOf('suspicious') !== -1) return 'SUSP';
    if (n.indexOf('medical') !== -1) return 'MED';
    if (n.indexOf('fire') !== -1) return 'FIRE';
    if (n.indexOf('vandal') !== -1) return 'VAND';
    if (n.indexOf('security breach') !== -1) return 'SEC';
    if (n.indexOf('theft') !== -1 || n.indexOf('burglary') !== -1) return 'THEFT';
    if (n.indexOf('equipment') !== -1) return 'EQUIP';
    if (n.indexOf('statement') !== -1) return 'STATEMENT';
    if (n.indexOf('found item') !== -1 || n === 'found') return 'FOUND ITEM';
    if (n.indexOf('return form') !== -1 || n.indexOf('return') !== -1) return 'RETURN FORM';
    if (n.indexOf('other') !== -1) return 'OTHER';
    return '';
  }

  function isStatementCategory(code, name) {
    var c = (code || '').toUpperCase();
    var n = (name || '').toLowerCase();
    return !!GP_STATEMENT_CODES[c] || n.indexOf('statement') !== -1;
  }

  function isFoundCategory(code, name) {
    var c = (code || '').toUpperCase();
    var n = (name || '').toLowerCase();
    return !!GP_FOUND_CODES[c] || n.indexOf('found item') !== -1;
  }

  function isReturnCategory(code, name) {
    var c = (code || '').toUpperCase();
    var n = (name || '').toLowerCase();
    return !!GP_RETURN_CODES[c] || n.indexOf('return form') !== -1;
  }

  function loadCategoriesFromDom() {
    var jsonEl = document.getElementById('gp-incident-categories-json');
    if (jsonEl && jsonEl.textContent) {
      try {
        var parsed = JSON.parse(jsonEl.textContent);
        if (Array.isArray(parsed) && parsed.length) {
          return parsed;
        }
      } catch (_e) { }
    }
    var el = document.getElementById('gp-cat-data');
    if (!el) return [];
    return Array.prototype.slice.call(el.options).map(function (o) {
      var code = o.getAttribute('data-code') || inferCodeFromCategoryName(o.text);
      return {
        id: parseInt(o.value, 10),
        n: o.text,
        code: code,
      };
    });
  }

  function filterCategoriesForType(type, all) {
    var codes = GP_TYPE_CATEGORY_CODES[type];
    if (!codes) {
      return all;
    }
    var filtered = all.filter(function (c) {
      return codes.indexOf(c.code) !== -1;
    });
    if (!filtered.length) {
      filtered = filterCategoriesByNameHints(type, all);
    }
    return filtered;
  }

  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/'/g, '&#39;');
  }

  function selectWizardCategory(id, name, code) {
    var catInput = document.getElementById('gp-inc-category');
    if (catInput) {
      catInput.value = String(id);
    }
    var container = document.getElementById('gp-cat-options');
    if (container) {
      container.querySelectorAll('.gp-cat-chip').forEach(function (btn) {
        btn.classList.toggle('selected', String(btn.dataset.id) === String(id));
      });
    }
    var resolvedCode = code || '';
    if (!resolvedCode && name) {
      resolvedCode = inferCodeFromCategoryName(name);
    }
    if (typeof toggleMobileIncidentCategoryFields === 'function') {
      toggleMobileIncidentCategoryFields(name || '', resolvedCode);
    } else {
      toggleCategoryExtraSections(name || '', resolvedCode);
    }
  }

  function toggleCategoryExtraSections(categoryName, categoryCode) {
    var statement = document.getElementById('mobile-statement-fields');
    var found = document.getElementById('mobile-found-fields');
    var ret = document.getElementById('mobile-return-fields');
    if (!statement || !found || !ret) return;
    statement.style.display = isStatementCategory(categoryCode, categoryName) ? 'block' : 'none';
    found.style.display = isFoundCategory(categoryCode, categoryName) ? 'block' : 'none';
    ret.style.display = isReturnCategory(categoryCode, categoryName) ? 'block' : 'none';
  }

  function renderCategoryOptions(type) {
    var container = document.getElementById('gp-cat-options');
    var hint = document.getElementById('gp-cat-type-hint');
    var legacyWrap = document.getElementById('gp-cat-wrap');
    var catInput = document.getElementById('gp-inc-category');
    if (!container) {
      return [];
    }

    if (legacyWrap) {
      legacyWrap.style.display = 'none';
    }
    if (typeof window.gpCatPicker !== 'undefined' && window.gpCatPicker.close) {
      window.gpCatPicker.close();
    }

    var all = window.GP_CATEGORIES || loadCategoriesFromDom();
    var filtered = filterCategoriesForType(type, all);
    window._gpFilteredCategories = filtered;

    var typeLabels = {
      suspicious_person: 'Suspicious Person',
      medical_emergency: 'Medical Emergency',
      property_damage: 'Property Damage',
      community_violation: 'Community Violation',
      parking_violation: 'Parking Violation',
      security_breach: 'Security Breach',
      equipment_malfunction: 'Equipment Issue',
      other: 'Other',
    };
    if (hint) {
      hint.textContent = filtered.length
        ? ('Choose a category for ' + (typeLabels[type] || 'this incident type') + ':')
        : 'No categories are configured for this incident type.';
    }

    container.innerHTML = '';
    if (!filtered.length) {
      if (catInput) catInput.value = '';
      return filtered;
    }

    if (filtered.length === 1) {
      var only = filtered[0];
      if (catInput) catInput.value = String(only.id);
      container.innerHTML =
        '<span class="gp-cat-selected-pill"><i class="fa fa-check me-1"></i>' +
        escapeHtml(only.n) + '</span>';
      return filtered;
    }

    filtered.forEach(function (c) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'gp-cat-chip';
      btn.dataset.id = String(c.id);
      btn.textContent = c.n;
      btn.addEventListener('click', function () {
        selectWizardCategory(c.id, c.n, c.code);
      });
      container.appendChild(btn);
    });

    var defaultCode = GP_TYPE_DEFAULT_CODE[type];
    var match = filtered.find(function (c) { return c.code === defaultCode; }) || filtered[0];
    if (match) {
      selectWizardCategory(match.id, match.n, match.code);
    }
    return filtered;
  }

  function filterCategoriesByNameHints(type, all) {
    var hints = GP_TYPE_CATEGORY_NAME_HINTS[type] || [];
    if (!hints.length) return [];
    return all.filter(function (c) {
      var n = (c.n || '').toLowerCase();
      return hints.some(function (h) { return n.indexOf(h) !== -1; });
    });
  }

  function inferWizardTypeFromTitle(title) {
    var t = (title || '').toLowerCase();
    if (t.indexOf('suspicious') !== -1) return 'suspicious_person';
    if (t.indexOf('medical') !== -1) return 'medical_emergency';
    if (t.indexOf('community') !== -1) return 'community_violation';
    if (t.indexOf('parking') !== -1 || t.indexOf('double park') !== -1) return 'parking_violation';
    if (t.indexOf('violation') !== -1) return 'community_violation';
    if (t.indexOf('property damage') !== -1 || t.indexOf('vandal') !== -1) return 'property_damage';
    if (t.indexOf('security breach') !== -1) return 'security_breach';
    if (t.indexOf('equipment') !== -1) return 'equipment_malfunction';
    return 'other';
  }

  function getActiveCategoryList() {
    if (window._gpWizardType) {
      if (window._gpFilteredCategories && window._gpFilteredCategories.length) {
        return window._gpFilteredCategories;
      }
      return filterCategoriesForType(window._gpWizardType, window.GP_CATEGORIES || loadCategoriesFromDom());
    }
    return [];
  }

  function showServerCategoryPanel(type) {
    if (window.gpIncidentWizard && window.gpIncidentWizard.showCategoryPanel) {
      window.gpIncidentWizard.showCategoryPanel(type);
      return true;
    }
    var panels = document.querySelectorAll('.gp-cat-type-panel');
    if (!panels.length) return false;
    panels.forEach(function (p) {
      p.style.display = (p.getAttribute('data-wizard-type') === type) ? '' : 'none';
    });
    var panel = document.querySelector('.gp-cat-type-panel[data-wizard-type="' + type + '"]');
    var catInput = document.getElementById('gp-inc-category');
    var catRow = document.getElementById('gp-cat-row');
    if (catRow) catRow.style.display = panel ? '' : 'none';
    if (!panel || !catInput) return true;
    var pill = panel.querySelector('.gp-cat-selected-pill[data-auto-id]');
    if (pill) {
      catInput.value = pill.getAttribute('data-auto-id');
      return true;
    }
    var defaultBtn = panel.querySelector('.gp-cat-chip[data-default="1"]') || panel.querySelector('.gp-cat-chip');
    if (defaultBtn) {
      catInput.value = defaultBtn.getAttribute('data-id');
      panel.querySelectorAll('.gp-cat-chip').forEach(function (b) {
        b.classList.toggle('selected', b === defaultBtn);
      });
    }
    return true;
  }

  function applyTypeCategoryFilter(type) {
    window._gpWizardType = type;
    try { sessionStorage.setItem('gp_inc_wizard_type', type); } catch (_e) {}
    var wizardTypeHidden = document.getElementById('gp-inc-wizard-type');
    if (wizardTypeHidden) wizardTypeHidden.value = type || '';

    if (showServerCategoryPanel(type)) {
      toggleWizardTypeFields(type);
      return window._gpFilteredCategories || [];
    }

    window.GP_CATEGORIES = loadCategoriesFromDom();
    var filtered = renderCategoryOptions(type);

    var catRow = document.getElementById('gp-cat-row');
    if (catRow) {
      catRow.style.display = filtered.length ? '' : 'none';
    }

    toggleWizardTypeFields(type);
    return filtered;
  }

  function toggleWizardTypeFields(type) {
    GP_WIZARD_TYPE_FIELDS.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    var showId = GP_WIZARD_TYPE_MAP[type];
    if (showId) {
      var block = document.getElementById(showId);
      if (block) block.style.display = 'block';
    }
    var hidden = document.getElementById('gp-inc-wizard-type');
    if (hidden) hidden.value = type || '';
  }

  function relayWizardTypeFields(form) {
    if (!form) return;
    form.querySelectorAll('input[data-type-relay]').forEach(function (h) { h.remove(); });

    var type = window._gpWizardType || '';
    var relayMap = {
      suspicious_person: [
        { name: 'persons_involved', id: 'gp-field-person-desc' },
        { name: 'witnesses', id: 'gp-field-witnesses' },
        { name: 'immediate_actions', id: 'gp-field-actions' },
        { name: 'police_notified', id: 'gp-field-police', checkbox: true },
      ],
      medical_emergency: [
        { name: 'persons_involved', id: 'gp-field-patient' },
        { name: 'injury_details', id: 'gp-field-condition' },
        { name: 'immediate_actions', id: 'gp-field-first-aid' },
        { name: 'ambulance_called', id: 'gp-field-ambulance', checkbox: true },
        { name: 'medical_required', id: 'gp-field-medical', checkbox: true },
      ],
      security_breach: [
        { name: 'persons_involved', id: 'gp-field-intruder' },
        { name: 'immediate_actions', id: 'gp-field-actions-sec' },
        { name: 'police_notified', id: 'gp-field-police-sec', checkbox: true },
        { name: 'property_damage', id: 'gp-field-items-missing', checkbox: true },
      ],
      property_damage: [
        { name: 'damage_details', id: 'gp-field-damage-type' },
        { name: 'immediate_actions', id: 'gp-field-actions-prop' },
        { name: 'property_damage', id: 'gp-field-property-damage', checkbox: true },
      ],
      community_violation: [
        { name: 'damage_details', id: 'gp-field-cv-details' },
        { name: 'immediate_actions', id: 'gp-field-cv-actions' },
        { name: 'persons_involved', id: 'gp-field-cv-person' },
      ],
      parking_violation: [
        { name: 'damage_details', id: 'gp-field-park-details' },
        { name: 'immediate_actions', id: 'gp-field-park-actions' },
        { name: 'persons_involved', id: 'gp-field-park-vehicle' },
      ],
      equipment_malfunction: [
        { name: 'location', id: 'gp-field-equipment-location' },
        { name: 'immediate_actions', id: 'gp-field-equipment-actions' },
        { name: 'damage_details', id: 'gp-field-equipment-issue' },
      ],
    };

    var fields = relayMap[type] || [];
    fields.forEach(function (spec) {
      var field = document.getElementById(spec.id);
      if (!field) return;
      var val = spec.checkbox ? (field.checked ? 'on' : '') : (field.value || '').trim();
      if (!val) return;
      var h = document.createElement('input');
      h.type = 'hidden';
      h.name = spec.name;
      h.value = val;
      h.dataset.typeRelay = type;
      form.appendChild(h);
    });
  }

  function wizardTypeFromCode(code) {
    return GP_CODE_TO_TYPE[code] || 'other';
  }

  function toggleDetailSectionsByCategory(categoryCode) {
    var sections = document.querySelectorAll('[data-gp-section]');
    if (!sections.length) return;

    var wizardType = wizardTypeFromCode(categoryCode);
    var allowed = GP_DETAIL_SECTIONS[wizardType];

    sections.forEach(function (el) {
      var key = el.getAttribute('data-gp-section');
      if (!allowed) {
        el.style.display = '';
        return;
      }
      el.style.display = allowed.indexOf(key) !== -1 ? '' : 'none';
    });

    var basicCard = document.getElementById('gp-inc-section-basic');
    if (basicCard) basicCard.style.display = '';
  }

  function filterDetailCategoryDropdown(categoryCode) {
    var select = document.getElementById('category_id');
    if (!select) return;

    var wizardType = wizardTypeFromCode(categoryCode);
    var allowedCodes = GP_TYPE_CATEGORY_CODES[wizardType];
    if (!allowedCodes) return;

    Array.prototype.forEach.call(select.options, function (opt) {
      if (!opt.value) return;
      var code = opt.getAttribute('data-code') || inferCodeFromCategoryName(opt.textContent || opt.text);
      opt.style.display = allowedCodes.indexOf(code) !== -1 ? '' : 'none';
      opt.disabled = allowedCodes.indexOf(code) === -1;
    });
  }

  function triggerPhotoInput(inputId) {
    var input = document.getElementById(inputId || 'incident_images');
    if (input) input.click();
  }

  window.GPIncidentMobile = {
    GP_TYPE_CATEGORY_CODES: GP_TYPE_CATEGORY_CODES,
    GP_TYPE_DEFAULT_CODE: GP_TYPE_DEFAULT_CODE,
    GP_CODE_TO_TYPE: GP_CODE_TO_TYPE,
    GP_STATEMENT_CODES: GP_STATEMENT_CODES,
    GP_FOUND_CODES: GP_FOUND_CODES,
    GP_RETURN_CODES: GP_RETURN_CODES,
    loadCategoriesFromDom: loadCategoriesFromDom,
    getActiveCategoryList: getActiveCategoryList,
    applyTypeCategoryFilter: applyTypeCategoryFilter,
    toggleWizardTypeFields: toggleWizardTypeFields,
    relayWizardTypeFields: relayWizardTypeFields,
    wizardTypeFromCode: wizardTypeFromCode,
    toggleDetailSectionsByCategory: toggleDetailSectionsByCategory,
    filterDetailCategoryDropdown: filterDetailCategoryDropdown,
    triggerPhotoInput: triggerPhotoInput,
    inferWizardTypeFromTitle: inferWizardTypeFromTitle,
    filterCategoriesByNameHints: filterCategoriesByNameHints,
    renderCategoryOptions: renderCategoryOptions,
    selectWizardCategory: selectWizardCategory,
    filterCategoriesForType: filterCategoriesForType,
    isStatementCategory: isStatementCategory,
    isFoundCategory: isFoundCategory,
    isReturnCategory: isReturnCategory,
    toggleCategoryExtraSections: toggleCategoryExtraSections,
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.GP_CATEGORIES = loadCategoriesFromDom();
    var detailRoot = document.getElementById('gp-incident-detail-root');
    if (detailRoot) {
      var code = detailRoot.getAttribute('data-category-code') || '';
      toggleDetailSectionsByCategory(code);
      filterDetailCategoryDropdown(code);
    }
  });
})();

/**
 * Client-side search + filter for mobile incident / community violation lists.
 * Markup: wrap lists in [data-gp-list-filter-root], items use .gp-filterable-item
 * with data-search / data-status / data-severity / data-category attributes.
 */
(function () {
  'use strict';

  function normalize(value) {
    return String(value || '').toLowerCase().trim();
  }

  function applyRoot(root) {
    if (!root) return;
    var q = normalize((root.querySelector('[data-gp-list-search]') || {}).value);
    var status = normalize((root.querySelector('[data-gp-list-status]') || {}).value);
    var severity = normalize((root.querySelector('[data-gp-list-severity]') || {}).value);
    var category = normalize((root.querySelector('[data-gp-list-category]') || {}).value);
    var items = root.querySelectorAll('.gp-filterable-item');
    var visible = 0;
    items.forEach(function (item) {
      var hay = normalize(item.getAttribute('data-search'));
      var itemStatus = normalize(item.getAttribute('data-status'));
      var itemSeverity = normalize(item.getAttribute('data-severity'));
      var itemCategory = normalize(item.getAttribute('data-category'));
      var matchQ = !q || hay.indexOf(q) !== -1;
      var matchStatus = !status || status === 'all' || itemStatus === status
        || (status === 'open' && ['submitted', 'under_review', 'investigating', 'draft'].indexOf(itemStatus) !== -1)
        || (status === 'closed' && ['resolved', 'closed'].indexOf(itemStatus) !== -1);
      var matchSeverity = !severity || severity === 'all' || itemSeverity === severity;
      var matchCategory = !category || category === 'all' || itemCategory === category;
      var show = matchQ && matchStatus && matchSeverity && matchCategory;
      item.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });
    var empty = root.querySelector('[data-gp-list-empty]');
    if (empty) {
      empty.style.display = visible ? 'none' : '';
    }
    var count = root.querySelector('[data-gp-list-count]');
    if (count) {
      count.textContent = visible + ' shown';
    }
    // Hide empty section cards when all children filtered out
    root.querySelectorAll('[data-gp-list-section]').forEach(function (section) {
      var sectionItems = section.querySelectorAll('.gp-filterable-item');
      if (!sectionItems.length) return;
      var any = false;
      sectionItems.forEach(function (el) {
        if (el.style.display !== 'none') any = true;
      });
      section.style.display = any ? '' : 'none';
    });
  }

  function bindRoot(root) {
    if (!root || root._gpListFilterBound) return;
    root._gpListFilterBound = true;
    var rerun = function () { applyRoot(root); };
    root.querySelectorAll('[data-gp-list-search], [data-gp-list-status], [data-gp-list-severity], [data-gp-list-category]')
      .forEach(function (el) {
        el.addEventListener('input', rerun);
        el.addEventListener('change', rerun);
      });
    var clearBtn = root.querySelector('[data-gp-list-clear]');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        root.querySelectorAll('[data-gp-list-search]').forEach(function (el) { el.value = ''; });
        root.querySelectorAll('[data-gp-list-status], [data-gp-list-severity], [data-gp-list-category]')
          .forEach(function (el) { el.value = 'all'; });
        applyRoot(root);
      });
    }
    applyRoot(root);
  }

  function initAll() {
    document.querySelectorAll('[data-gp-list-filter-root]').forEach(bindRoot);
  }

  window.GPIncidentListFilter = {
    init: initAll,
    apply: applyRoot,
    bind: bindRoot,
  };

  document.addEventListener('DOMContentLoaded', initAll);
})();
