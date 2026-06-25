/* @ds-bundle: {"format":3,"namespace":"CRMDesignSystem_acff3b","components":[],"sourceHashes":{"ui_kits/crm/components/AppShell.jsx":"09140d50f45b","ui_kits/crm/components/Billing.jsx":"000a9e110593","ui_kits/crm/components/Calendar.jsx":"78ad09275cc8","ui_kits/crm/components/Chats.jsx":"65cbe9c5b13b","ui_kits/crm/components/ClientCard.jsx":"86db3598be31","ui_kits/crm/components/Dashboard.jsx":"cd79e4bcb26f","ui_kits/crm/components/Leads.jsx":"979045fc90ce","ui_kits/crm/components/Reports.jsx":"15d4b281cf0c","ui_kits/crm/components/Schedule.jsx":"b97002c870e6","ui_kits/crm/components/primitives.jsx":"fd67e8cba4fa"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.CRMDesignSystem_acff3b = window.CRMDesignSystem_acff3b || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// ui_kits/crm/components/AppShell.jsx
try { (() => {
// AppShell — sidebar + topbar
function AppShell({
  active,
  onNavigate,
  children,
  title,
  search
}) {
  const nav = [{
    id: 'dashboard',
    label: 'Дашборд',
    icon: 'home'
  }, {
    id: 'leads',
    label: 'Лиды',
    icon: 'kanban',
    badge: 12
  }, {
    id: 'chats',
    label: 'Чаты',
    icon: 'chat',
    badge: 3
  }, {
    id: 'client',
    label: 'Клиенты',
    icon: 'user'
  }, {
    id: 'calendar',
    label: 'Календарь',
    icon: 'cal'
  }, {
    id: 'schedule',
    label: 'Расписание',
    icon: 'clock'
  }, {
    id: 'reports',
    label: 'Отчёты',
    icon: 'chart'
  }, {
    id: 'billing',
    label: 'Тариф',
    icon: 'card'
  }];
  return /*#__PURE__*/React.createElement("div", {
    className: "app"
  }, /*#__PURE__*/React.createElement("aside", {
    className: "sidebar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "brand"
  }, /*#__PURE__*/React.createElement("div", {
    className: "brand-mark"
  }), /*#__PURE__*/React.createElement("span", {
    className: "brand-name"
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439")), nav.map(n => /*#__PURE__*/React.createElement("button", {
    key: n.id,
    className: `nav-item ${active === n.id ? 'active' : ''}`,
    onClick: () => onNavigate(n.id)
  }, /*#__PURE__*/React.createElement(Icon, {
    name: n.icon,
    size: 18,
    className: "nav-icon"
  }), /*#__PURE__*/React.createElement("span", null, n.label), n.badge ? /*#__PURE__*/React.createElement("span", {
    className: "nav-badge"
  }, n.badge) : null)), /*#__PURE__*/React.createElement("div", {
    className: "nav-group"
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439"), /*#__PURE__*/React.createElement("button", {
    className: "nav-item"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "sparkle",
    size: 18,
    className: "nav-icon"
  }), "AI-\u043F\u043E\u043C\u043E\u0449\u043D\u0438\u043A"), /*#__PURE__*/React.createElement("button", {
    className: "nav-item"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 18,
    className: "nav-icon"
  }), "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438"), /*#__PURE__*/React.createElement("div", {
    className: "user-card"
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: "\u041B\u0435\u043D\u0430 \u041E\u0440\u043B\u043E\u0432\u0430",
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "name"
  }, "\u041B\u0435\u043D\u0430 \u041E\u0440\u043B\u043E\u0432\u0430"), /*#__PURE__*/React.createElement("div", {
    className: "role"
  }, "\u0421\u0442\u0443\u0434\u0438\u044F \xAB\u041B\u0430\u043A\xBB")), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "more",
    size: 16
  })))), /*#__PURE__*/React.createElement("div", {
    className: "main"
  }, /*#__PURE__*/React.createElement("div", {
    className: "topbar"
  }, /*#__PURE__*/React.createElement("span", {
    className: "title"
  }, title), search !== false && /*#__PURE__*/React.createElement("div", {
    className: "search"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 16,
    style: {
      color: 'var(--fg-3)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    placeholder: "\u041F\u043E\u0438\u0441\u043A \u043A\u043B\u0438\u0435\u043D\u0442\u043E\u0432, \u043B\u0438\u0434\u043E\u0432, \u0441\u043E\u0431\u044B\u0442\u0438\u0439\u2026"
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 18
  }))), /*#__PURE__*/React.createElement("div", {
    className: "content"
  }, children)));
}
window.AppShell = AppShell;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/AppShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Billing.jsx
try { (() => {
// Billing — тариф и оплата
function Billing() {
  const plans = [{
    id: 'start',
    name: 'Старт',
    price: 1490,
    per: 'мес',
    features: ['1 мастер', 'до 100 лидов/мес', 'Telegram', 'базовый AI'],
    current: false
  }, {
    id: 'pro',
    name: 'Про',
    price: 3490,
    per: 'мес',
    features: ['до 5 мастеров', 'безлимит лидов', 'TG + IG + WA', 'AI-администратор', 'календарь и SMS'],
    current: true
  }, {
    id: 'team',
    name: 'Команда',
    price: 7990,
    per: 'мес',
    features: ['до 20 мастеров', 'API + интеграции', 'выделенный AI', 'аналитика и отчёты', 'приоритетная поддержка'],
    current: false
  }];
  const invoices = [{
    date: '01 апр 2026',
    plan: 'Про',
    sum: 3490,
    status: 'paid'
  }, {
    date: '01 мар 2026',
    plan: 'Про',
    sum: 3490,
    status: 'paid'
  }, {
    date: '01 фев 2026',
    plan: 'Про',
    sum: 3490,
    status: 'paid'
  }, {
    date: '01 янв 2026',
    plan: 'Про',
    sum: 3490,
    status: 'paid'
  }, {
    date: '01 дек 2025',
    plan: 'Старт → Про',
    sum: 2490,
    status: 'paid'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block",
    style: {
      display: 'grid',
      gridTemplateColumns: '1.6fr 1fr 1fr',
      gap: 18,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-overline",
    style: {
      marginBottom: 6
    }
  }, "\u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u0442\u0430\u0440\u0438\u0444"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 600
    }
  }, "\u041F\u0440\u043E"), /*#__PURE__*/React.createElement("span", {
    className: "chip chip-won"
  }, "\u0410\u043A\u0442\u0438\u0432\u0435\u043D")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: 'var(--fg-2)',
      marginTop: 4
    }
  }, "\u0421\u043B\u0435\u0434\u0443\u044E\u0449\u0435\u0435 \u0441\u043F\u0438\u0441\u0430\u043D\u0438\u0435 \u2014 1 \u043C\u0430\u044F, \u0441\u043F\u0438\u0448\u0435\u0442\u0441\u044F 3 490 \u20BD \u0441 \u043A\u0430\u0440\u0442\u044B \u2022\u2022 4452.")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-overline",
    style: {
      marginBottom: 6
    }
  }, "\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u043D\u043E"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      marginBottom: 6
    }
  }, "3 \u0438\u0437 5 \u043C\u0430\u0441\u0442\u0435\u0440\u043E\u0432"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 6,
      background: 'var(--ark-gray-100)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: '60%',
      height: '100%',
      background: 'var(--accent)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      marginTop: 10,
      marginBottom: 6
    }
  }, "1 248 \u043B\u0438\u0434\u043E\u0432 \u0432 \u044D\u0442\u043E\u043C \u043C\u0435\u0441\u044F\u0446\u0435"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--fg-3)',
      fontFamily: 'var(--font-mono)'
    }
  }, "\u0431\u0435\u0437\u043B\u0438\u043C\u0438\u0442")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, "\u041F\u0435\u0440\u0435\u0439\u0442\u0438 \u043D\u0430 \xAB\u041A\u043E\u043C\u0430\u043D\u0434\u0443\xBB"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0421\u043C\u0435\u043D\u0438\u0442\u044C \u043A\u0430\u0440\u0442\u0443"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-ghost btn-sm",
    style: {
      color: 'var(--ark-red-600)'
    }
  }, "\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u043E\u0434\u043F\u0438\u0441\u043A\u0443"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title",
    style: {
      marginBottom: 10,
      paddingLeft: 2
    }
  }, "\u0422\u0430\u0440\u0438\u0444\u044B"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 12
    }
  }, plans.map(p => /*#__PURE__*/React.createElement("div", {
    key: p.id,
    className: "card-block",
    style: {
      borderColor: p.current ? 'var(--accent)' : 'var(--border-1)',
      boxShadow: p.current ? '0 0 0 2px rgba(42,138,240,.15)' : 'none',
      position: 'relative'
    }
  }, p.current && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: -1,
      right: 14,
      background: 'var(--accent)',
      color: '#fff',
      fontSize: 11,
      fontWeight: 600,
      padding: '3px 10px',
      borderRadius: '0 0 4px 4px'
    }
  }, "\u0412\u0430\u0448 \u0442\u0430\u0440\u0438\u0444"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      marginBottom: 6
    }
  }, p.name), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 6,
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 28,
      fontWeight: 600,
      letterSpacing: '-0.01em',
      fontFeatureSettings: "'tnum'"
    }
  }, p.price.toLocaleString('ru-RU'), " \u20BD"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: 'var(--fg-3)'
    }
  }, "/ ", p.per)), /*#__PURE__*/React.createElement("ul", {
    style: {
      margin: 0,
      padding: 0,
      listStyle: 'none',
      display: 'flex',
      flexDirection: 'column',
      gap: 7,
      fontSize: 13,
      color: 'var(--fg-1)'
    }
  }, p.features.map((f, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14,
    style: {
      transform: 'rotate(45deg)',
      color: 'var(--accent)',
      marginTop: 3,
      flex: 'none'
    }
  }), f))), /*#__PURE__*/React.createElement("button", {
    className: `btn ${p.current ? 'btn-secondary' : 'btn-primary'} btn-sm`,
    style: {
      marginTop: 14,
      width: '100%',
      justifyContent: 'center'
    }
  }, p.current ? 'Текущий' : p.price > 3490 ? 'Перейти' : 'Понизить'))))), /*#__PURE__*/React.createElement("div", {
    className: "dash-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0421\u043F\u043E\u0441\u043E\u0431 \u043E\u043F\u043B\u0430\u0442\u044B"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      alignItems: 'center',
      padding: '10px 12px',
      border: '1px solid var(--border-2)',
      borderRadius: 8,
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 42,
      height: 28,
      borderRadius: 4,
      background: 'linear-gradient(135deg,#1F2733,#3A4452)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontWeight: 700,
      fontSize: 11,
      letterSpacing: '.05em'
    }
  }, "VISA"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontFamily: 'var(--font-mono)'
    }
  }, "\u2022\u2022 \u2022\u2022 \u2022\u2022 4452"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--fg-3)'
    }
  }, "\u0418\u0441\u0442\u0435\u043A\u0430\u0435\u0442 09 / 28")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-ghost btn-sm"
  }, "\u0423\u0434\u0430\u043B\u0438\u0442\u044C")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14
  }), "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u043A\u0430\u0440\u0442\u0443")), /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u043F\u043B\u0430\u0442\u0435\u0436\u0435\u0439"), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      fontSize: 13,
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      textAlign: 'left',
      color: 'var(--fg-3)',
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      fontWeight: 500
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '6px 0',
      fontWeight: 500
    }
  }, "\u0414\u0430\u0442\u0430"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '6px 0',
      fontWeight: 500
    }
  }, "\u0422\u0430\u0440\u0438\u0444"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '6px 0',
      fontWeight: 500,
      textAlign: 'right'
    }
  }, "\u0421\u0443\u043C\u043C\u0430"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '6px 0',
      fontWeight: 500,
      textAlign: 'right',
      width: 90
    }
  }))), /*#__PURE__*/React.createElement("tbody", null, invoices.map((inv, i) => /*#__PURE__*/React.createElement("tr", {
    key: i,
    style: {
      borderTop: '1px solid var(--border-2)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 0',
      fontFamily: 'var(--font-mono)',
      color: 'var(--fg-2)',
      fontSize: 12
    }
  }, inv.date), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 0'
    }
  }, inv.plan), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 0',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      textAlign: 'right'
    }
  }, inv.sum.toLocaleString('ru-RU'), " \u20BD"), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 0',
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    className: "t-link",
    style: {
      fontSize: 12
    }
  }, "\u0427\u0435\u043A")))))))));
}
window.Billing = Billing;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Billing.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Calendar.jsx
try { (() => {
// Calendar — week view
const DAYS = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];
const HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19];
const SEED_EVENTS = [{
  day: 0,
  start: 10,
  dur: 1.5,
  title: 'Маникюр',
  client: 'Аня Петрова',
  master: 'Лена',
  color: 'blue'
}, {
  day: 0,
  start: 14,
  dur: 2,
  title: 'Педикюр + покрытие',
  client: 'Мария Кравченко',
  master: 'Лена',
  color: 'green'
}, {
  day: 1,
  start: 11,
  dur: 1,
  title: 'Маникюр',
  client: 'Таня Соколова',
  master: 'Оля',
  color: 'blue'
}, {
  day: 1,
  start: 16,
  dur: 1.5,
  title: 'Дизайн',
  client: 'Лена Шарова',
  master: 'Лена',
  color: 'violet'
}, {
  day: 2,
  start: 9.5,
  dur: 1.5,
  title: 'Маникюр + френч',
  client: 'Ирина Елисеева',
  master: 'Оля',
  color: 'blue'
}, {
  day: 2,
  start: 14,
  dur: 1,
  title: 'Маникюр',
  client: 'Аня Петрова',
  master: 'Лена',
  color: 'blue'
}, {
  day: 3,
  start: 12,
  dur: 2,
  title: 'Спа-педикюр',
  client: 'Полина Юрова',
  master: 'Лена',
  color: 'green'
}, {
  day: 4,
  start: 10,
  dur: 1,
  title: 'Снятие',
  client: 'Вика Носова',
  master: 'Оля',
  color: 'yellow'
}, {
  day: 4,
  start: 15,
  dur: 2,
  title: 'Маникюр + дизайн',
  client: 'Дарья Романова',
  master: 'Лена',
  color: 'violet'
}, {
  day: 5,
  start: 11,
  dur: 1.5,
  title: 'Маникюр',
  client: 'Ольга Климова',
  master: 'Оля',
  color: 'blue'
}];
const SLOT_H = 56; // px per hour
const FIRST_HOUR = HOURS[0];
function Calendar() {
  const [view, setView] = useState('week');
  return /*#__PURE__*/React.createElement("div", {
    className: "calendar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cal-toolbar"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0421\u0435\u0433\u043E\u0434\u043D\u044F"), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevL",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevR",
    size: 18
  })), /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "21 \u2013 27 \u0430\u043F\u0440\u0435\u043B\u044F 2026"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "cal-tabs"
  }, /*#__PURE__*/React.createElement("button", {
    className: view === 'month' ? 'active' : '',
    onClick: () => setView('month')
  }, "\u041C\u0435\u0441\u044F\u0446"), /*#__PURE__*/React.createElement("button", {
    className: view === 'week' ? 'active' : '',
    onClick: () => setView('week')
  }, "\u041D\u0435\u0434\u0435\u043B\u044F"), /*#__PURE__*/React.createElement("button", {
    className: view === 'day' ? 'active' : '',
    onClick: () => setView('day')
  }, "\u0414\u0435\u043D\u044C")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14
  }), "\u041D\u043E\u0432\u043E\u0435 \u0441\u043E\u0431\u044B\u0442\u0438\u0435")), /*#__PURE__*/React.createElement("div", {
    className: "cal-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cal-corner"
  }), DAYS.map((d, i) => /*#__PURE__*/React.createElement("div", {
    key: d,
    className: `cal-day-head ${i === 2 ? 'today' : ''}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "day-name"
  }, d), /*#__PURE__*/React.createElement("span", {
    className: "day-num"
  }, 21 + i))), /*#__PURE__*/React.createElement("div", {
    className: "cal-times"
  }, HOURS.map(h => /*#__PURE__*/React.createElement("div", {
    key: h,
    className: "cal-time-slot",
    style: {
      height: SLOT_H
    }
  }, h, ":00"))), DAYS.map((d, dayIdx) => /*#__PURE__*/React.createElement("div", {
    key: d,
    className: "cal-day-col"
  }, HOURS.map(h => /*#__PURE__*/React.createElement("div", {
    key: h,
    className: "grid-line",
    style: {
      height: SLOT_H
    }
  })), SEED_EVENTS.filter(e => e.day === dayIdx).map((e, i) => {
    const top = (e.start - FIRST_HOUR) * SLOT_H + 2;
    const height = e.dur * SLOT_H - 4;
    const hh = Math.floor(e.start);
    const mm = Math.round((e.start - hh) * 60);
    const endH = e.start + e.dur;
    const ehh = Math.floor(endH);
    const emm = Math.round((endH - ehh) * 60);
    const fmt = (h, m) => `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: `cal-event ev-${e.color}`,
      style: {
        top,
        height
      },
      draggable: true
    }, /*#__PURE__*/React.createElement("div", {
      className: "e-time"
    }, fmt(hh, mm), "\u2013", fmt(ehh, emm)), /*#__PURE__*/React.createElement("div", {
      className: "e-title"
    }, e.title), /*#__PURE__*/React.createElement("div", {
      className: "e-client"
    }, e.client, " \xB7 ", e.master));
  })))));
}
window.Calendar = Calendar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Calendar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Chats.jsx
try { (() => {
// Chats — Telegram-style messenger
const SEED_CHATS = [{
  id: 1,
  name: 'Аня Петрова',
  src: 'TG',
  last: 'Аркадий: записал на маникюр, 25 апр',
  time: '14:02',
  unread: 2,
  online: true
}, {
  id: 2,
  name: 'Таня Соколова',
  src: 'IG',
  last: 'Спасибо! До встречи',
  time: '13:48',
  unread: 0,
  sent: true
}, {
  id: 3,
  name: 'Ирина Елисеева',
  src: 'WA',
  last: 'Можно перенести на пятницу?',
  time: '12:10',
  unread: 1
}, {
  id: 4,
  name: 'Мария Кравченко',
  src: 'IG',
  last: 'А есть слот на вечер?',
  time: '11:32',
  unread: 0,
  sent: true
}, {
  id: 5,
  name: 'Дарья Романова',
  src: 'TG',
  last: 'Здравствуйте, хочу записаться',
  time: 'вчера',
  unread: 0
}, {
  id: 6,
  name: 'Лена Шарова',
  src: 'TG',
  last: 'Спасибо большое!',
  time: 'вчера',
  unread: 0,
  sent: true
}, {
  id: 7,
  name: 'Вика Носова',
  src: 'TG',
  last: 'Окей',
  time: 'пн',
  unread: 0,
  sent: true
}];
const SEED_THREAD = [{
  day: 'Сегодня'
}, {
  kind: 'in',
  text: 'Здравствуйте! Можно записаться на маникюр на эту неделю?',
  time: '14:00'
}, {
  kind: 'ai',
  text: 'Конечно. Какое время удобнее — утро или вечер?'
}, {
  kind: 'in',
  text: 'Лучше после обеда, в среду',
  time: '14:01'
}, {
  kind: 'ai',
  text: 'Есть свободные слоты в среду 25 апреля: 13:00, 14:00 и 17:30. Какой подойдёт?'
}, {
  kind: 'in',
  text: 'Давайте 14:00',
  time: '14:02'
}, {
  kind: 'out',
  text: 'Записал на 25 апр в 14:00. Подтвердить?',
  time: '14:02',
  read: true
}];
function Chats() {
  const [activeId, setActiveId] = useState(1);
  const [thread, setThread] = useState(SEED_THREAD);
  const [draft, setDraft] = useState('');
  const active = SEED_CHATS.find(c => c.id === activeId);
  const send = () => {
    if (!draft.trim()) return;
    setThread(t => [...t, {
      kind: 'out',
      text: draft,
      time: 'сейчас',
      read: false
    }]);
    setDraft('');
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "chats",
    style: {
      margin: '-18px -24px',
      height: 'calc(100% + 36px)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "chat-list"
  }, /*#__PURE__*/React.createElement("div", {
    className: "chat-list-header"
  }, /*#__PURE__*/React.createElement("div", {
    className: "search"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 16,
    style: {
      color: 'var(--fg-3)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    placeholder: "\u041F\u043E\u0438\u0441\u043A \u043F\u0435\u0440\u0435\u043F\u0438\u0441\u043E\u043A"
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 18
  }))), /*#__PURE__*/React.createElement("div", {
    className: "chat-list-rows"
  }, SEED_CHATS.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.id,
    className: `chat-row ${c.id === activeId ? 'active' : ''}`,
    onClick: () => setActiveId(c.id)
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: c.name,
    size: "md"
  }), /*#__PURE__*/React.createElement("div", {
    className: "body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "top"
  }, /*#__PURE__*/React.createElement("span", {
    className: "name"
  }, c.name, /*#__PURE__*/React.createElement("span", {
    className: `src src-${c.src.toLowerCase()}`
  }, c.src)), /*#__PURE__*/React.createElement("span", {
    className: "time"
  }, c.time)), /*#__PURE__*/React.createElement("div", {
    className: "preview"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, c.last), c.unread ? /*#__PURE__*/React.createElement("span", {
    className: "badge"
  }, c.unread) : c.sent ? /*#__PURE__*/React.createElement("span", {
    className: "read"
  }, "\u2713\u2713") : null)))))), /*#__PURE__*/React.createElement("div", {
    className: "chat-pane"
  }, /*#__PURE__*/React.createElement("div", {
    className: "chat-header"
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: active.name,
    size: "md"
  }), /*#__PURE__*/React.createElement("div", {
    className: "info"
  }, /*#__PURE__*/React.createElement("div", {
    className: "name"
  }, active.name), /*#__PURE__*/React.createElement("div", {
    className: "status"
  }, active.online ? 'в сети' : 'был(а) недавно', " \xB7 ", active.src === 'TG' ? 'Telegram' : active.src === 'IG' ? 'Instagram' : 'WhatsApp')), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "phone",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "user",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "more",
    size: 18
  }))), /*#__PURE__*/React.createElement("div", {
    className: "chat-thread"
  }, thread.map((m, i) => {
    if (m.day) return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: "thread-day"
    }, m.day);
    if (m.kind === 'ai') return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: "msg ai"
    }, /*#__PURE__*/React.createElement("div", {
      className: "ai-name"
    }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439"), m.text);
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: `msg ${m.kind}`
    }, m.text, /*#__PURE__*/React.createElement("span", {
      className: "meta"
    }, m.time, m.kind === 'out' && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)'
      }
    }, m.read ? '✓✓' : '✓')));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 18px',
      background: '#fff'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "ai-suggestion"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "sparkle",
    size: 16,
    style: {
      color: 'var(--accent)',
      marginTop: 2
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "label"
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439 \u043F\u0440\u0435\u0434\u043B\u0430\u0433\u0430\u0435\u0442"), /*#__PURE__*/React.createElement("div", {
    className: "text"
  }, "\xAB\u0425\u043E\u0440\u043E\u0448\u043E, \u0436\u0434\u0443 \u0432\u0430\u0441 25 \u0430\u043F\u0440\u0435\u043B\u044F \u0432 14:00. \u0417\u0430 \u0434\u0435\u043D\u044C \u0434\u043E \u0432\u0438\u0437\u0438\u0442\u0430 \u043F\u0440\u0438\u0448\u043B\u044E \u043D\u0430\u043F\u043E\u043C\u0438\u043D\u0430\u043D\u0438\u0435.\xBB")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm",
    onClick: () => setDraft('Хорошо, жду вас 25 апреля в 14:00. За день до визита пришлю напоминание.')
  }, "\u0412\u0441\u0442\u0430\u0432\u0438\u0442\u044C"))), /*#__PURE__*/React.createElement("div", {
    className: "composer"
  }, /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "paperclip",
    size: 20
  })), /*#__PURE__*/React.createElement("div", {
    className: "input-wrap"
  }, /*#__PURE__*/React.createElement("textarea", {
    placeholder: "\u041D\u0430\u043F\u0438\u0448\u0438\u0442\u0435 \u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435\u2026",
    value: draft,
    rows: 1,
    onChange: e => setDraft(e.target.value),
    onKeyDown: e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    }
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "smile",
    size: 20
  })), draft.trim() ? /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm",
    onClick: send,
    style: {
      height: 36,
      width: 36,
      padding: 0,
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "send",
    size: 16
  })) : /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "mic",
    size: 20
  })))));
}
window.Chats = Chats;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Chats.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/ClientCard.jsx
try { (() => {
// ClientCard — full-width table list + popup detail
const SOURCE_CLASS = {
  TG: 'src-tg',
  IG: 'src-ig',
  WA: 'src-wa',
  VK: 'src-vk',
  MAX: 'src-max',
  'Сайт': 'src-web'
};
const CLIENTS = [{
  id: 1,
  name: 'Аня Петрова',
  phone: '+7 999 123-45-67',
  src: 'TG',
  visits: 7,
  spent: 28400,
  avg: 4057,
  ltv: 'A',
  last: '12 апр',
  next: '25 апр',
  master: 'Лена'
}, {
  id: 2,
  name: 'Мария Кравченко',
  phone: '+7 916 555-22-11',
  src: 'IG',
  visits: 5,
  spent: 21000,
  avg: 4200,
  ltv: 'B',
  last: '08 апр',
  next: null,
  master: 'Лена'
}, {
  id: 3,
  name: 'Таня Соколова',
  phone: '+7 905 234-19-22',
  src: 'WA',
  visits: 12,
  spent: 39600,
  avg: 3300,
  ltv: 'A',
  last: '20 апр',
  next: '04 май',
  master: 'Оля'
}, {
  id: 4,
  name: 'Ольга Климова',
  phone: '+7 926 781-04-55',
  src: 'IG',
  visits: 1,
  spent: 3500,
  avg: 3500,
  ltv: 'C',
  last: '03 апр',
  next: null,
  master: 'Оля'
}, {
  id: 5,
  name: 'Ирина Елисеева',
  phone: '+7 968 333-71-08',
  src: 'WA',
  visits: 4,
  spent: 18200,
  avg: 4550,
  ltv: 'B',
  last: '15 апр',
  next: '28 апр',
  master: 'Лена'
}, {
  id: 6,
  name: 'Дарья Романова',
  phone: '+7 901 209-44-12',
  src: 'Сайт',
  visits: 0,
  spent: 0,
  avg: 0,
  ltv: '—',
  last: '—',
  next: null,
  master: '—'
}, {
  id: 7,
  name: 'Лена Шарова',
  phone: '+7 977 144-33-22',
  src: 'TG',
  visits: 9,
  spent: 35100,
  avg: 3900,
  ltv: 'A',
  last: '18 апр',
  next: '02 май',
  master: 'Лена'
}, {
  id: 8,
  name: 'Вика Носова',
  phone: '+7 985 100-65-49',
  src: 'TG',
  visits: 6,
  spent: 17400,
  avg: 2900,
  ltv: 'B',
  last: '11 апр',
  next: null,
  master: 'Оля'
}, {
  id: 9,
  name: 'Полина Юрова',
  phone: '+7 903 444-72-91',
  src: 'IG',
  visits: 3,
  spent: 12300,
  avg: 4100,
  ltv: 'C',
  last: '06 апр',
  next: '24 апр',
  master: 'Лена'
}, {
  id: 10,
  name: 'Маша Беликова',
  phone: '+7 962 011-83-14',
  src: 'Сайт',
  visits: 2,
  spent: 7200,
  avg: 3600,
  ltv: 'C',
  last: '10 мар',
  next: null,
  master: 'Оля'
}, {
  id: 11,
  name: 'Юля Антонова',
  phone: '+7 999 678-22-91',
  src: 'TG',
  visits: 8,
  spent: 31200,
  avg: 3900,
  ltv: 'A',
  last: '17 апр',
  next: '01 май',
  master: 'Лена'
}];
const ANYA_DETAIL = {
  prefs: ['Не любит запах ацетона', 'Аллергия на Kodi', 'Нюдовые оттенки'],
  next: {
    date: '25 апреля',
    time: '14:00',
    service: 'Маникюр + покрытие',
    master: 'Лена'
  },
  visitsLog: [{
    date: '12 апр',
    service: 'Маникюр',
    master: 'Лена',
    price: 3500,
    status: 'done'
  }, {
    date: '29 мар',
    service: 'Маникюр + френч',
    master: 'Лена',
    price: 4200,
    status: 'done'
  }, {
    date: '15 мар',
    service: 'Снятие + маникюр',
    master: 'Оля',
    price: 4500,
    status: 'done'
  }, {
    date: '01 мар',
    service: 'Маникюр',
    master: 'Лена',
    price: 3500,
    status: 'done'
  }, {
    date: '14 фев',
    service: 'Спа-маникюр',
    master: 'Лена',
    price: 4900,
    status: 'done'
  }],
  ai: 'Я заметил, Аня ходит каждые 3 недели. Следующий визит должен быть около 16 мая — могу написать ей за 2 дня и предложить слот?'
};
function ClientPopup({
  client,
  onClose
}) {
  if (!client) return null;
  const d = ANYA_DETAIL;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(15,22,32,.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      animation: 'fadeIn 180ms'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: 720,
      maxHeight: '82vh',
      background: '#fff',
      borderRadius: 12,
      boxShadow: 'var(--shadow-3)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '18px 20px',
      borderBottom: '1px solid var(--border-2)',
      display: 'flex',
      gap: 14,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: client.name,
    size: "lg"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 18,
      fontWeight: 600
    }
  }, client.name), /*#__PURE__*/React.createElement("span", {
    className: SOURCE_CLASS[client.src],
    style: {
      fontSize: 11,
      padding: '2px 6px',
      borderRadius: 4,
      fontWeight: 600
    }
  }, client.src), client.ltv !== '—' && /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      background: 'var(--ark-violet-100)',
      color: 'var(--ark-violet-500)'
    }
  }, client.ltv, " VIP")), /*#__PURE__*/React.createElement("div", {
    className: "t-mono",
    style: {
      fontSize: 12,
      color: 'var(--fg-2)',
      marginTop: 2
    }
  }, client.phone)), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn",
    onClick: onClose
  }, /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 6l12 12M6 18 18 6"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '16px 20px',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4,1fr)',
      gap: 0,
      padding: '10px 0',
      borderTop: '1px solid var(--border-2)',
      borderBottom: '1px solid var(--border-2)'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption"
  }, "\u0412\u0438\u0437\u0438\u0442\u044B"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 18,
      fontWeight: 600
    }
  }, client.visits)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption"
  }, "\u041F\u043E\u0442\u0440\u0430\u0442\u0438\u043B\u0430"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 18,
      fontWeight: 600
    }
  }, client.spent.toLocaleString('ru-RU'), " \u20BD")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption"
  }, "\u0421\u0440. \u0447\u0435\u043A"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 18,
      fontWeight: 600
    }
  }, client.avg.toLocaleString('ru-RU'), " \u20BD")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption"
  }, "\u041C\u0430\u0441\u0442\u0435\u0440"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 500,
      paddingTop: 4
    }
  }, client.master))), client.id === 1 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      padding: '10px 12px',
      background: 'var(--ark-blue-50)',
      borderRadius: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 24,
      height: 24,
      borderRadius: 6,
      background: 'var(--accent)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "sparkle",
    size: 14,
    style: {
      color: '#fff'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      fontSize: 13,
      color: 'var(--ark-blue-700)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      marginBottom: 2
    }
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439"), /*#__PURE__*/React.createElement("div", null, d.ai))), client.next && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      alignItems: 'center',
      padding: '10px 12px',
      border: '1px solid var(--border-2)',
      borderRadius: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 44,
      height: 44,
      background: 'var(--ark-blue-50)',
      borderRadius: 6,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      color: 'var(--ark-blue-700)',
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, "\u0430\u043F\u0440"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 16,
      fontWeight: 600,
      color: 'var(--ark-blue-700)',
      lineHeight: 1
    }
  }, client.next.split(' ')[0])), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600
    }
  }, client.id === 1 ? d.next.service : 'Маникюр'), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: 'var(--fg-2)'
    }
  }, client.id === 1 ? d.next.time : '12:00', " \xB7 \u043C\u0430\u0441\u0442\u0435\u0440 ", client.master)), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u041F\u0435\u0440\u0435\u043D\u0435\u0441\u0442\u0438")), client.id === 1 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption",
    style: {
      marginBottom: 6
    }
  }, "\u041E\u0441\u043E\u0431\u0435\u043D\u043D\u043E\u0441\u0442\u0438"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 6
    }
  }, d.prefs.map((p, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    className: "chip",
    style: {
      background: 'var(--bg-panel)',
      color: 'var(--fg-1)'
    }
  }, p)))), client.visits > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "t-caption",
    style: {
      marginBottom: 6
    }
  }, "\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0432\u0438\u0437\u0438\u0442\u043E\u0432"), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      fontSize: 13,
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("tbody", null, (client.id === 1 ? d.visitsLog : d.visitsLog.slice(0, Math.min(client.visits, 4))).map((v, i) => /*#__PURE__*/React.createElement("tr", {
    key: i,
    style: {
      borderTop: '1px solid var(--border-2)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '7px 0',
      fontFamily: 'var(--font-mono)',
      color: 'var(--fg-2)',
      fontSize: 12,
      width: 64
    }
  }, v.date), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '7px 0'
    }
  }, v.service, " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--fg-3)'
    }
  }, "\xB7 ", v.master)), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '7px 0',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      textAlign: 'right',
      width: 80
    }
  }, v.price.toLocaleString('ru-RU'), " \u20BD"))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 20px',
      borderTop: '1px solid var(--border-2)',
      display: 'flex',
      gap: 8,
      justifyContent: 'flex-end',
      background: 'var(--bg-panel-2)'
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chat",
    size: 14
  }), "\u041D\u0430\u043F\u0438\u0441\u0430\u0442\u044C"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "cal",
    size: 14
  }), "\u0417\u0430\u043F\u0438\u0441\u0430\u0442\u044C"))));
}
function ClientCard() {
  const [openId, setOpenId] = useState(null);
  const [src, setSrc] = useState('all');
  const [sort, setSort] = useState('last');
  const [q, setQ] = useState('');
  const list = CLIENTS.filter(c => src === 'all' || c.src === src).filter(c => !q || c.name.toLowerCase().includes(q.toLowerCase()) || c.phone.includes(q));
  const open = openId ? CLIENTS.find(c => c.id === openId) : null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      minHeight: 0,
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "toolbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "search",
    style: {
      height: 32,
      background: 'var(--bg-panel)',
      borderRadius: 6,
      padding: '0 10px',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      width: 280
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 16,
    style: {
      color: 'var(--fg-3)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    value: q,
    onChange: e => setQ(e.target.value),
    placeholder: "\u0418\u043C\u044F \u0438\u043B\u0438 \u0442\u0435\u043B\u0435\u0444\u043E\u043D",
    style: {
      background: 'transparent',
      border: 0,
      outline: 0,
      flex: 1,
      font: 'inherit',
      fontSize: 13
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "tab-pill"
  }, /*#__PURE__*/React.createElement("button", {
    className: src === 'all' ? 'active' : '',
    onClick: () => setSrc('all')
  }, "\u0412\u0441\u0435"), /*#__PURE__*/React.createElement("button", {
    className: src === 'TG' ? 'active' : '',
    onClick: () => setSrc('TG')
  }, "Telegram"), /*#__PURE__*/React.createElement("button", {
    className: src === 'IG' ? 'active' : '',
    onClick: () => setSrc('IG')
  }, "Instagram"), /*#__PURE__*/React.createElement("button", {
    className: src === 'WA' ? 'active' : '',
    onClick: () => setSrc('WA')
  }, "WhatsApp")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "filter",
    size: 14
  }), "\u0421\u0435\u0433\u043C\u0435\u043D\u0442"), /*#__PURE__*/React.createElement("div", {
    className: "grow"
  }), /*#__PURE__*/React.createElement("span", {
    className: "t-caption"
  }, "\u041D\u0430\u0439\u0434\u0435\u043D\u043E: ", list.length), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14
  }), "\u041D\u043E\u0432\u044B\u0439 \u043A\u043B\u0438\u0435\u043D\u0442")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0,
      overflow: 'auto',
      background: '#fff',
      border: '1px solid var(--border-1)',
      borderRadius: 8
    }
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: 13
    }
  }, /*#__PURE__*/React.createElement("thead", {
    style: {
      position: 'sticky',
      top: 0,
      background: 'var(--bg-panel-2)',
      zIndex: 1
    }
  }, /*#__PURE__*/React.createElement("tr", {
    style: {
      textAlign: 'left',
      color: 'var(--fg-3)',
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      fontWeight: 500
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500
    }
  }, "\u041A\u043B\u0438\u0435\u043D\u0442"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500
    }
  }, "\u0422\u0435\u043B\u0435\u0444\u043E\u043D"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 60,
      textAlign: 'center'
    }
  }, "\u041A\u0430\u043D\u0430\u043B"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 80,
      textAlign: 'right',
      cursor: 'pointer'
    },
    onClick: () => setSort('visits')
  }, "\u0412\u0438\u0437\u0438\u0442\u044B ", sort === 'visits' ? '↓' : ''), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 120,
      textAlign: 'right',
      cursor: 'pointer'
    },
    onClick: () => setSort('spent')
  }, "\u041F\u043E\u0442\u0440\u0430\u0442\u0438\u043B\u0430 ", sort === 'spent' ? '↓' : ''), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 100,
      cursor: 'pointer'
    },
    onClick: () => setSort('last')
  }, "\u0411\u044B\u043B(\u0430) ", sort === 'last' ? '↓' : ''), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 110
    }
  }, "\u0421\u043B\u0435\u0434\u0443\u044E\u0449\u0438\u0439"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 80
    }
  }, "\u041C\u0430\u0441\u0442\u0435\u0440"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      width: 40
    }
  }))), /*#__PURE__*/React.createElement("tbody", null, list.map(c => /*#__PURE__*/React.createElement("tr", {
    key: c.id,
    onClick: () => setOpenId(c.id),
    style: {
      borderTop: '1px solid var(--border-2)',
      cursor: 'pointer'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'var(--bg-hover)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: c.name,
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600
    }
  }, c.name), c.ltv === 'A' && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: 'var(--ark-violet-500)',
      fontWeight: 600,
      letterSpacing: '.04em'
    }
  }, "A \xB7 VIP")))), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: 'var(--fg-2)'
    }
  }, c.phone), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: SOURCE_CLASS[c.src],
    style: {
      fontSize: 10,
      padding: '2px 6px',
      borderRadius: 3,
      fontWeight: 600
    }
  }, c.src)), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600
    }
  }, c.visits || '—'), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 500
    }
  }, c.spent ? c.spent.toLocaleString('ru-RU') + ' ₽' : '—'), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      color: 'var(--fg-2)'
    }
  }, c.last), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px'
    }
  }, c.next ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--ark-blue-700)',
      fontWeight: 500
    }
  }, c.next) : /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--fg-3)'
    }
  }, "\u2014")), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      color: 'var(--fg-2)'
    }
  }, c.master), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      color: 'var(--fg-3)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevR",
    size: 16
  }))))))), /*#__PURE__*/React.createElement(ClientPopup, {
    client: open,
    onClose: () => setOpenId(null)
  }));
}
window.ClientCard = ClientCard;
window.ClientPopup = ClientPopup;
window.CLIENTS = CLIENTS;
window.SOURCE_CLASS = SOURCE_CLASS;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/ClientCard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Dashboard.jsx
try { (() => {
// Dashboard
function Sparkline({
  data,
  color = '#2A8AF0',
  w = 120,
  h = 36
}) {
  const max = Math.max(...data),
    min = Math.min(...data);
  const pts = data.map((v, i) => {
    const x = i / (data.length - 1) * (w - 4) + 2;
    const y = h - 2 - (v - min) / (max - min || 1) * (h - 4);
    return `${x},${y}`;
  }).join(' ');
  return /*#__PURE__*/React.createElement("svg", {
    width: w,
    height: h
  }, /*#__PURE__*/React.createElement("polyline", {
    points: pts,
    fill: "none",
    stroke: color,
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }));
}
function BarChart({
  data,
  w = 480,
  h = 180
}) {
  const max = Math.max(...data.map(d => d.value));
  const barW = (w - 40) / data.length - 8;
  return /*#__PURE__*/React.createElement("svg", {
    width: w,
    height: h,
    style: {
      display: 'block'
    }
  }, [0, 0.25, 0.5, 0.75, 1].map(t => /*#__PURE__*/React.createElement("line", {
    key: t,
    x1: "32",
    x2: w,
    y1: h - 24 - t * (h - 40),
    y2: h - 24 - t * (h - 40),
    stroke: "#ECEFF2",
    strokeWidth: "1"
  })), data.map((d, i) => {
    const x = 32 + i * (barW + 8);
    const barH = d.value / max * (h - 40);
    return /*#__PURE__*/React.createElement("g", {
      key: i
    }, /*#__PURE__*/React.createElement("rect", {
      x: x,
      y: h - 24 - barH,
      width: barW,
      height: barH,
      rx: "3",
      fill: d.color || '#2A8AF0'
    }), /*#__PURE__*/React.createElement("text", {
      x: x + barW / 2,
      y: h - 8,
      fontSize: "10",
      fill: "#5B6573",
      textAnchor: "middle",
      fontFamily: "JetBrains Mono"
    }, d.label));
  }));
}
function Donut({
  segments,
  size = 140
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = size / 2 - 14;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size
  }, /*#__PURE__*/React.createElement("circle", {
    cx: c,
    cy: c,
    r: r,
    fill: "none",
    stroke: "#F4F6F8",
    strokeWidth: "14"
  }), segments.map((s, i) => {
    const len = s.value / total * circumference;
    const el = /*#__PURE__*/React.createElement("circle", {
      key: i,
      cx: c,
      cy: c,
      r: r,
      fill: "none",
      stroke: s.color,
      strokeWidth: "14",
      strokeDasharray: `${len} ${circumference - len}`,
      strokeDashoffset: -offset,
      transform: `rotate(-90 ${c} ${c})`
    });
    offset += len;
    return el;
  }), /*#__PURE__*/React.createElement("text", {
    x: c,
    y: c - 2,
    textAnchor: "middle",
    fontSize: "22",
    fontWeight: "600",
    fill: "#0F1620",
    fontFamily: "Inter"
  }, total), /*#__PURE__*/React.createElement("text", {
    x: c,
    y: c + 14,
    textAnchor: "middle",
    fontSize: "11",
    fill: "#5B6573",
    fontFamily: "Inter"
  }, "\u0432\u0441\u0435\u0433\u043E"));
}
function Dashboard() {
  const tasks = [{
    time: '10:30',
    text: 'Я перезвоню Ане Петровой — подтвердить запись',
    author: 'Аркадий'
  }, {
    time: '11:00',
    text: 'Мария Кравченко — предложу акцию на педикюр',
    author: 'Аркадий'
  }, {
    time: '14:00',
    text: 'Подтвердить визит Тани Соколовой',
    author: 'вы поставили'
  }, {
    time: '16:30',
    text: 'Я свяжусь с лидом из Instagram (Ольга К.)',
    author: 'Аркадий'
  }, {
    time: '17:00',
    text: 'Я отправлю отзывную форму после визита Иры Е.',
    author: 'Аркадий'
  }];
  const sources = [{
    color: '#2A8AF0',
    value: 42,
    label: 'Telegram'
  }, {
    color: '#E26B7E',
    value: 28,
    label: 'Instagram'
  }, {
    color: '#16A34A',
    value: 18,
    label: 'WhatsApp'
  }, {
    color: '#C9A227',
    value: 12,
    label: 'Сайт'
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "kpi-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u041B\u0438\u0434\u044B \u0437\u0430 \u043D\u0435\u0434\u0435\u043B\u044E"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "128"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "delta up"
  }, "\u25B2 12%"), /*#__PURE__*/React.createElement(Sparkline, {
    data: [8, 12, 9, 14, 18, 15, 22]
  }))), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u041A\u043E\u043D\u0432\u0435\u0440\u0441\u0438\u044F"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "34%"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "delta up"
  }, "\u25B2 4 \u043F.\u043F."), /*#__PURE__*/React.createElement(Sparkline, {
    data: [28, 30, 29, 32, 31, 33, 34],
    color: "#16A34A"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u0412\u044B\u0440\u0443\u0447\u043A\u0430"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "487 \u041A\xA0\u20BD"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "delta down"
  }, "\u25BC 3%"), /*#__PURE__*/React.createElement(Sparkline, {
    data: [60, 62, 58, 55, 52, 50, 49],
    color: "#DC4646"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u0421\u0440\u0435\u0434\u043D\u0438\u0439 \u0447\u0435\u043A"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "3 920 \u20BD"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "delta flat"
  }, "\u2014 0%"), /*#__PURE__*/React.createElement(Sparkline, {
    data: [39, 40, 39, 40, 39, 40, 39],
    color: "#5B6573"
  })))), /*#__PURE__*/React.createElement("div", {
    className: "dash-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u041B\u0438\u0434\u044B \u043F\u043E \u0434\u043D\u044F\u043C", /*#__PURE__*/React.createElement("button", {
    className: "btn btn-ghost btn-sm"
  }, "\u041D\u0435\u0434\u0435\u043B\u044F \u25BE")), /*#__PURE__*/React.createElement(BarChart, {
    data: [{
      label: 'Пн',
      value: 12
    }, {
      label: 'Вт',
      value: 18
    }, {
      label: 'Ср',
      value: 14
    }, {
      label: 'Чт',
      value: 22
    }, {
      label: 'Пт',
      value: 28
    }, {
      label: 'Сб',
      value: 19
    }, {
      label: 'Вс',
      value: 15
    }],
    w: 520,
    h: 200
  })), /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u0438"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(Donut, {
    segments: sources
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 6
    }
  }, sources.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.label,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 8,
      borderRadius: 2,
      background: s.color
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      color: 'var(--fg-1)'
    }
  }, s.label), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      color: 'var(--fg-2)'
    }
  }, s.value))))))), /*#__PURE__*/React.createElement("div", {
    className: "dash-grid",
    style: {
      gridTemplateColumns: '1fr 1fr'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0411\u043B\u0438\u0436\u0430\u0439\u0448\u0438\u0435 \u0437\u0430\u0434\u0430\u0447\u0438 \u0410\u0440\u043A\u0430\u0434\u0438\u044F", /*#__PURE__*/React.createElement("button", {
    className: "btn btn-ghost btn-sm"
  }, "\u0412\u0441\u0435")), tasks.map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "task-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "task-check"
  }), /*#__PURE__*/React.createElement("div", {
    className: "task-time"
  }, t.time), /*#__PURE__*/React.createElement("div", {
    className: "task-text"
  }, /*#__PURE__*/React.createElement("div", null, t.text), /*#__PURE__*/React.createElement("div", {
    className: "task-author"
  }, t.author))))), /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0412\u043E\u0440\u043E\u043D\u043A\u0430", /*#__PURE__*/React.createElement("span", {
    className: "t-caption"
  }, "\u0437\u0430 30 \u0434\u043D\u0435\u0439")), [{
    name: 'Новый',
    value: 240,
    pct: 100,
    color: '#9AA3AE'
  }, {
    name: 'Контакт',
    value: 168,
    pct: 70,
    color: '#2A8AF0'
  }, {
    name: 'Квалифицирован',
    value: 96,
    pct: 40,
    color: '#E0A21A'
  }, {
    name: 'Выигран',
    value: 54,
    pct: 22,
    color: '#16A34A'
  }].map(s => /*#__PURE__*/React.createElement("div", {
    key: s.name,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '10px 0',
      borderTop: '1px solid var(--border-2)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 140,
      fontSize: 13
    }
  }, s.name), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 8,
      background: 'var(--ark-gray-100)',
      borderRadius: 4,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${s.pct}%`,
      height: '100%',
      background: s.color,
      borderRadius: 4
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 48,
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      fontWeight: 600,
      textAlign: 'right'
    }
  }, s.value))))));
}
window.Dashboard = Dashboard;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Dashboard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Leads.jsx
try { (() => {
// Leads — Kanban + List, channel labels, opens client popup on click
const COLUMNS = [{
  id: 'new',
  title: 'Новый',
  color: '#9AA3AE'
}, {
  id: 'contact',
  title: 'Контакт',
  color: '#2A8AF0'
}, {
  id: 'qualified',
  title: 'Квалифицирован',
  color: '#E0A21A'
}, {
  id: 'won',
  title: 'Выигран',
  color: '#16A34A'
}];
const SRC_CLASS = {
  'Telegram': 'src-tg',
  'Instagram': 'src-ig',
  'WhatsApp': 'src-wa',
  'VK': 'src-vk',
  'MAX': 'src-max',
  'Сайт': 'src-web'
};

// Map lead.src to a CLIENTS row (by name) — opens the same client popup
const SEED_LEADS = [{
  id: 1,
  name: 'Аня Петрова',
  phone: '+7 999 123-45-67',
  price: 4500,
  src: 'Telegram',
  status: 'contact',
  ai: 'Я записал на маникюр, 25 апр 14:00. Жду подтверждения.',
  clientId: 1
}, {
  id: 2,
  name: 'Мария Кравченко',
  phone: '+7 916 555-22-11',
  price: 6200,
  src: 'Instagram',
  status: 'qualified',
  ai: 'Предложу акцию на педикюр — была 2 раза в месяц.',
  clientId: 2
}, {
  id: 3,
  name: 'Таня Соколова',
  phone: '+7 905 234-19-22',
  price: 3200,
  src: 'WhatsApp',
  status: 'won',
  ai: null,
  clientId: 3
}, {
  id: 4,
  name: 'Ольга Климова',
  phone: '+7 926 781-04-55',
  price: 0,
  src: 'Instagram',
  status: 'new',
  ai: 'Новый клиент. Я завёл карточку, передаю вам.',
  clientId: 4
}, {
  id: 5,
  name: 'Ирина Елисеева',
  phone: '+7 968 333-71-08',
  price: 5400,
  src: 'Telegram',
  status: 'contact',
  ai: null,
  clientId: 5
}, {
  id: 6,
  name: 'Дарья Романова',
  phone: '+7 901 209-44-12',
  price: 0,
  src: 'MAX',
  status: 'new',
  ai: null,
  clientId: 6
}, {
  id: 7,
  name: 'Лена Шарова',
  phone: '+7 977 144-33-22',
  price: 7800,
  src: 'Telegram',
  status: 'qualified',
  ai: 'Я предложил слот в субботу — спрашивала про французский.',
  clientId: 7
}, {
  id: 8,
  name: 'Вика Носова',
  phone: '+7 985 100-65-49',
  price: 2900,
  src: 'Telegram',
  status: 'won',
  ai: null,
  clientId: 8
}, {
  id: 9,
  name: 'Полина Юрова',
  phone: '+7 903 444-72-91',
  price: 4100,
  src: 'MAX',
  status: 'contact',
  ai: 'Написала в MAX, ждёт подбор времени.',
  clientId: 9
}, {
  id: 10,
  name: 'Маша Беликова',
  phone: '+7 962 011-83-14',
  price: 0,
  src: 'Сайт',
  status: 'new',
  ai: null,
  clientId: 10
}];
function LeadCard({
  lead,
  dragging,
  onDragStart,
  onDragEnd,
  onClick
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: `lead-card ${dragging ? 'dragging' : ''}`,
    draggable: true,
    onDragStart: onDragStart,
    onDragEnd: onDragEnd,
    onClick: onClick
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'center',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: lead.name,
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 6,
      minHeight: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "name",
    style: {
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      lineHeight: '18px'
    }
  }, lead.name), /*#__PURE__*/React.createElement("span", {
    className: `src ${SRC_CLASS[lead.src] || ''}`,
    style: {
      flex: 'none'
    }
  }, lead.src)), /*#__PURE__*/React.createElement("div", {
    className: "phone"
  }, lead.phone))), lead.ai && /*#__PURE__*/React.createElement("div", {
    className: "ai-note"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ai-dot"
  }), /*#__PURE__*/React.createElement("span", null, lead.ai)), /*#__PURE__*/React.createElement("div", {
    className: "row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "price"
  }, lead.price ? `${lead.price.toLocaleString('ru-RU')} ₽` : '—')));
}
function LeadsKanban({
  leads,
  setLeads,
  onOpen
}) {
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);
  const onDragStart = id => setDragId(id);
  const onDragEnd = () => {
    setDragId(null);
    setOverCol(null);
  };
  const onDrop = status => {
    if (dragId == null) return;
    setLeads(ls => ls.map(l => l.id === dragId ? {
      ...l,
      status
    } : l));
    setDragId(null);
    setOverCol(null);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "kanban"
  }, COLUMNS.map(col => {
    const items = leads.filter(l => l.status === col.id);
    return /*#__PURE__*/React.createElement("div", {
      key: col.id,
      className: "kanban-col"
    }, /*#__PURE__*/React.createElement("div", {
      className: "kanban-col-header"
    }, /*#__PURE__*/React.createElement("span", {
      className: "colorbar",
      style: {
        background: col.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        fontWeight: 600
      }
    }, col.title), /*#__PURE__*/React.createElement("span", {
      className: "count"
    }, items.length), /*#__PURE__*/React.createElement("button", {
      className: "icon-btn",
      style: {
        width: 22,
        height: 22
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 14
    }))), /*#__PURE__*/React.createElement("div", {
      className: `kanban-list ${overCol === col.id ? 'drop-target' : ''}`,
      onDragOver: e => {
        e.preventDefault();
        setOverCol(col.id);
      },
      onDragLeave: () => setOverCol(c => c === col.id ? null : c),
      onDrop: () => onDrop(col.id)
    }, items.length === 0 && /*#__PURE__*/React.createElement("div", {
      className: "empty"
    }, "\u041F\u0443\u0441\u0442\u043E"), items.map(l => /*#__PURE__*/React.createElement(LeadCard, {
      key: l.id,
      lead: l,
      dragging: dragId === l.id,
      onDragStart: () => onDragStart(l.id),
      onDragEnd: onDragEnd,
      onClick: () => onOpen(l)
    }))));
  }));
}
function LeadsList({
  leads,
  setLeads,
  onOpen
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0,
      overflow: 'auto',
      background: '#fff',
      border: '1px solid var(--border-1)',
      borderRadius: 8
    }
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: 13
    }
  }, /*#__PURE__*/React.createElement("thead", {
    style: {
      position: 'sticky',
      top: 0,
      background: 'var(--bg-panel-2)',
      zIndex: 1
    }
  }, /*#__PURE__*/React.createElement("tr", {
    style: {
      textAlign: 'left',
      color: 'var(--fg-3)',
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      fontWeight: 500
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500
    }
  }, "\u041B\u0438\u0434"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 160
    }
  }, "\u0422\u0435\u043B\u0435\u0444\u043E\u043D"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 100,
      textAlign: 'center'
    }
  }, "\u041A\u0430\u043D\u0430\u043B"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 160
    }
  }, "\u042D\u0442\u0430\u043F"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500,
      width: 120,
      textAlign: 'right'
    }
  }, "\u0421\u0443\u043C\u043C\u0430"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      fontWeight: 500
    }
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '10px 14px',
      width: 40
    }
  }))), /*#__PURE__*/React.createElement("tbody", null, leads.map(l => /*#__PURE__*/React.createElement("tr", {
    key: l.id,
    onClick: () => onOpen(l),
    style: {
      borderTop: '1px solid var(--border-2)',
      cursor: 'pointer'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'var(--bg-hover)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: l.name,
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600
    }
  }, l.name))), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: 'var(--fg-2)'
    }
  }, l.phone), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: SRC_CLASS[l.src],
    style: {
      fontSize: 10,
      padding: '2px 6px',
      borderRadius: 3,
      fontWeight: 600,
      letterSpacing: '.02em'
    }
  }, l.src)), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px'
    }
  }, /*#__PURE__*/React.createElement(Chip, {
    kind: l.status
  }, STATUS_LABEL[l.status])), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600
    }
  }, l.price ? l.price.toLocaleString('ru-RU') + ' ₽' : '—'), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      color: 'var(--fg-2)',
      fontSize: 12,
      maxWidth: 340,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, l.ai ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: 'var(--accent)',
      flex: 'none'
    }
  }), l.ai) : /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--fg-3)'
    }
  }, "\u2014")), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '10px 14px',
      color: 'var(--fg-3)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevR",
    size: 16
  })))))));
}
function Leads() {
  const [leads, setLeads] = useState(SEED_LEADS);
  const [view, setView] = useState('kanban');
  const [openClient, setOpenClient] = useState(null);

  // Resolve a lead to a client object (use real CLIENT row if available, otherwise synthesize)
  const openLead = lead => {
    const real = (window.CLIENTS || []).find(c => c.id === lead.clientId);
    if (real) {
      setOpenClient(real);
      return;
    }
    // synthesize a minimal client for popup compatibility
    setOpenClient({
      id: lead.clientId || lead.id,
      name: lead.name,
      phone: lead.phone,
      src: {
        'Telegram': 'TG',
        'Instagram': 'IG',
        'WhatsApp': 'WA',
        'VK': 'VK',
        'MAX': 'MAX',
        'Сайт': 'Сайт'
      }[lead.src] || 'Сайт',
      visits: 0,
      spent: 0,
      avg: 0,
      ltv: '—',
      last: '—',
      next: null,
      master: '—'
    });
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "toolbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "tab-pill"
  }, /*#__PURE__*/React.createElement("button", {
    className: view === 'kanban' ? 'active' : '',
    onClick: () => setView('kanban')
  }, "\u041A\u0430\u043D\u0431\u0430\u043D"), /*#__PURE__*/React.createElement("button", {
    className: view === 'list' ? 'active' : '',
    onClick: () => setView('list')
  }, "\u0421\u043F\u0438\u0441\u043E\u043A")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "filter",
    size: 14
  }), "\u0412\u0441\u0435 \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u0438"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0412\u0441\u0435 \u043C\u0430\u0441\u0442\u0435\u0440\u0430"), /*#__PURE__*/React.createElement("div", {
    className: "grow"
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14
  }), "\u041D\u043E\u0432\u044B\u0439 \u043B\u0438\u0434")), view === 'kanban' ? /*#__PURE__*/React.createElement(LeadsKanban, {
    leads: leads,
    setLeads: setLeads,
    onOpen: openLead
  }) : /*#__PURE__*/React.createElement(LeadsList, {
    leads: leads,
    setLeads: setLeads,
    onOpen: openLead
  }), window.ClientPopup && /*#__PURE__*/React.createElement(window.ClientPopup, {
    client: openClient,
    onClose: () => setOpenClient(null)
  }));
}
window.Leads = Leads;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Leads.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Reports.jsx
try { (() => {
// Reports — отчёты
function Reports() {
  const months = ['Ноя', 'Дек', 'Янв', 'Фев', 'Мар', 'Апр'];
  const revenue = [320, 380, 420, 410, 460, 487]; // в тыс. ₽
  const visits = [82, 96, 110, 105, 124, 128];
  const max = Math.max(...revenue);
  const byService = [{
    name: 'Маникюр',
    value: 142,
    sum: 213000,
    color: '#2A8AF0'
  }, {
    name: 'Маникюр + покрытие',
    value: 86,
    sum: 198400,
    color: '#7E5CF0'
  }, {
    name: 'Педикюр',
    value: 38,
    sum: 95000,
    color: '#16A34A'
  }, {
    name: 'Дизайн',
    value: 22,
    sum: 44000,
    color: '#E0A21A'
  }, {
    name: 'Снятие',
    value: 18,
    sum: 18000,
    color: '#B85F9E'
  }];
  const totalSrv = byService.reduce((s, x) => s + x.value, 0);
  const byMaster = [{
    name: 'Лена',
    visits: 96,
    revenue: 287000,
    occ: 92,
    retention: 78
  }, {
    name: 'Оля',
    visits: 64,
    revenue: 144000,
    occ: 71,
    retention: 68
  }, {
    name: 'Маргарита',
    visits: 28,
    revenue: 56000,
    occ: 48,
    retention: 52
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "toolbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "tab-pill"
  }, /*#__PURE__*/React.createElement("button", null, "\u0414\u0435\u043D\u044C"), /*#__PURE__*/React.createElement("button", null, "\u041D\u0435\u0434\u0435\u043B\u044F"), /*#__PURE__*/React.createElement("button", {
    className: "active"
  }, "\u041C\u0435\u0441\u044F\u0446"), /*#__PURE__*/React.createElement("button", null, "\u041A\u0432\u0430\u0440\u0442\u0430\u043B"), /*#__PURE__*/React.createElement("button", null, "\u0413\u043E\u0434")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0412\u0441\u0435 \u043C\u0430\u0441\u0442\u0435\u0440\u0430"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0412\u0441\u0435 \u0443\u0441\u043B\u0443\u0433\u0438"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u042D\u043A\u0441\u043F\u043E\u0440\u0442 CSV")), /*#__PURE__*/React.createElement("div", {
    className: "kpi-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u0412\u044B\u0440\u0443\u0447\u043A\u0430"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "487 \u041A \u20BD"), /*#__PURE__*/React.createElement("span", {
    className: "delta up"
  }, "\u25B2 6%")), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u0412\u0438\u0437\u0438\u0442\u044B"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "128"), /*#__PURE__*/React.createElement("span", {
    className: "delta up"
  }, "\u25B2 4")), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u041D\u043E\u0432\u044B\u0435 \u043A\u043B\u0438\u0435\u043D\u0442\u044B"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "22"), /*#__PURE__*/React.createElement("span", {
    className: "delta up"
  }, "\u25B2 12%")), /*#__PURE__*/React.createElement("div", {
    className: "kpi"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-label"
  }, "\u0412\u043E\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u043C\u043E\u0441\u0442\u044C"), /*#__PURE__*/React.createElement("div", {
    className: "kpi-value"
  }, "68%"), /*#__PURE__*/React.createElement("span", {
    className: "delta down"
  }, "\u25BC 2 \u043F.\u043F."))), /*#__PURE__*/React.createElement("div", {
    className: "dash-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u0412\u044B\u0440\u0443\u0447\u043A\u0430 \u0438 \u0432\u0438\u0437\u0438\u0442\u044B \u043F\u043E \u043C\u0435\u0441\u044F\u0446\u0430\u043C"), /*#__PURE__*/React.createElement("svg", {
    width: "100%",
    height: "220",
    viewBox: "0 0 600 220",
    preserveAspectRatio: "none",
    style: {
      display: 'block'
    }
  }, [0, 0.25, 0.5, 0.75, 1].map(t => /*#__PURE__*/React.createElement("line", {
    key: t,
    x1: "40",
    x2: "590",
    y1: 20 + t * 160,
    y2: 20 + t * 160,
    stroke: "#ECEFF2",
    strokeWidth: "1"
  })), revenue.map((v, i) => {
    const x = 60 + i * 90;
    const h = v / max * 160;
    return /*#__PURE__*/React.createElement("g", {
      key: i
    }, /*#__PURE__*/React.createElement("rect", {
      x: x - 18,
      y: 20 + 160 - h,
      width: "36",
      height: h,
      rx: "3",
      fill: "#2A8AF0",
      opacity: i === revenue.length - 1 ? 1 : 0.7
    }), /*#__PURE__*/React.createElement("text", {
      x: x,
      y: 205,
      fontSize: "11",
      fontFamily: "JetBrains Mono",
      fill: "#5B6573",
      textAnchor: "middle"
    }, months[i]), /*#__PURE__*/React.createElement("text", {
      x: x,
      y: 20 + 160 - h - 6,
      fontSize: "10",
      fontFamily: "JetBrains Mono",
      fill: "#0F1620",
      textAnchor: "middle",
      fontWeight: "600"
    }, v, "\u041A"));
  }), /*#__PURE__*/React.createElement("polyline", {
    points: visits.map((v, i) => `${60 + i * 90},${20 + 160 - v / 140 * 160}`).join(' '),
    fill: "none",
    stroke: "#16A34A",
    strokeWidth: "2",
    strokeLinecap: "round"
  }), visits.map((v, i) => /*#__PURE__*/React.createElement("circle", {
    key: i,
    cx: 60 + i * 90,
    cy: 20 + 160 - v / 140 * 160,
    r: "3",
    fill: "#16A34A"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      fontSize: 12,
      color: 'var(--fg-2)',
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      background: '#2A8AF0',
      borderRadius: 2
    }
  }), "\u0412\u044B\u0440\u0443\u0447\u043A\u0430, \u0442\u044B\u0441. \u20BD"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 14,
      height: 2,
      background: '#16A34A'
    }
  }), "\u0412\u0438\u0437\u0438\u0442\u044B"))), /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u041F\u043E \u0443\u0441\u043B\u0443\u0433\u0430\u043C"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, byService.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.name
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 13,
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", null, s.name), /*#__PURE__*/React.createElement("span", {
    className: "t-mono",
    style: {
      fontWeight: 600
    }
  }, s.sum.toLocaleString('ru-RU'), " \u20BD")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 6,
      background: 'var(--ark-gray-100)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${s.value / totalSrv * 100}%`,
      height: '100%',
      background: s.color,
      borderRadius: 3
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--fg-3)',
      marginTop: 2,
      fontFamily: 'var(--font-mono)'
    }
  }, s.value, " \u0432\u0438\u0437\u0438\u0442\u043E\u0432 \xB7 ", Math.round(s.value / totalSrv * 100), "%")))))), /*#__PURE__*/React.createElement("div", {
    className: "card-block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-block-title"
  }, "\u041F\u043E \u043C\u0430\u0441\u0442\u0435\u0440\u0430\u043C", /*#__PURE__*/React.createElement("button", {
    className: "btn btn-ghost btn-sm"
  }, "\u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435")), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      fontSize: 13,
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      textAlign: 'left',
      color: 'var(--fg-3)',
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      fontWeight: 500
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '8px 0',
      fontWeight: 500
    }
  }, "\u041C\u0430\u0441\u0442\u0435\u0440"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '8px 0',
      fontWeight: 500,
      textAlign: 'right',
      width: 100
    }
  }, "\u0412\u0438\u0437\u0438\u0442\u044B"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '8px 0',
      fontWeight: 500,
      textAlign: 'right',
      width: 140
    }
  }, "\u0412\u044B\u0440\u0443\u0447\u043A\u0430"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '8px 0',
      fontWeight: 500,
      width: 200
    }
  }, "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: '8px 0',
      fontWeight: 500,
      width: 200
    }
  }, "\u0412\u043E\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u043C\u043E\u0441\u0442\u044C"))), /*#__PURE__*/React.createElement("tbody", null, byMaster.map(m => /*#__PURE__*/React.createElement("tr", {
    key: m.name,
    style: {
      borderTop: '1px solid var(--border-2)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '12px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: m.name,
    size: "sm"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 500
    }
  }, m.name))), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '12px 0',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600
    }
  }, m.visits), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '12px 0',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600
    }
  }, m.revenue.toLocaleString('ru-RU'), " \u20BD"), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '12px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 6,
      background: 'var(--ark-gray-100)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${m.occ}%`,
      height: '100%',
      background: m.occ > 80 ? '#16A34A' : m.occ > 60 ? '#E0A21A' : '#DC4646',
      borderRadius: 3
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      width: 32,
      textAlign: 'right'
    }
  }, m.occ, "%"))), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '12px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 6,
      background: 'var(--ark-gray-100)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${m.retention}%`,
      height: '100%',
      background: '#2A8AF0',
      borderRadius: 3
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      width: 32,
      textAlign: 'right'
    }
  }, m.retention, "%")))))))), /*#__PURE__*/React.createElement("div", {
    className: "card-block",
    style: {
      borderColor: 'var(--ark-blue-100)',
      background: 'var(--ark-blue-50)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 32,
      height: 32,
      borderRadius: 8,
      background: 'var(--accent)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "sparkle",
    size: 18,
    style: {
      color: '#fff'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--ark-blue-700)',
      marginBottom: 4
    }
  }, "\u0410\u0440\u043A\u0430\u0434\u0438\u0439 \u0437\u0430\u043C\u0435\u0442\u0438\u043B"), /*#__PURE__*/React.createElement("ul", {
    style: {
      margin: 0,
      paddingLeft: 18,
      fontSize: 14,
      color: 'var(--fg-1)',
      display: 'flex',
      flexDirection: 'column',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("li", null, "\u0423 \u041C\u0430\u0440\u0433\u0430\u0440\u0438\u0442\u044B \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0441\u0435\u0433\u043E 48% \u2014 \u043C\u043E\u0433\u0443 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0438\u0442\u044C \u0435\u0439 \u0441\u043B\u043E\u0442\u044B \u043F\u043E\u0434 \u0430\u043A\u0446\u0438\u044E \u0434\u043B\u044F \u043D\u043E\u0432\u044B\u0445 \u043A\u043B\u0438\u0435\u043D\u0442\u043E\u0432?"), /*#__PURE__*/React.createElement("li", null, "\u0412\u043E\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u043C\u043E\u0441\u0442\u044C \u0443\u043F\u0430\u043B\u0430 \u043D\u0430 2 \u043F.\u043F. \u2014 14 \u043A\u043B\u0438\u0435\u043D\u0442\u043E\u0432 \u043D\u0435 \u0432\u0435\u0440\u043D\u0443\u043B\u0438\u0441\u044C \u043F\u043E\u0441\u043B\u0435 \u043F\u0435\u0440\u0432\u043E\u0433\u043E \u0432\u0438\u0437\u0438\u0442\u0430. \u0421\u0434\u0435\u043B\u0430\u0442\u044C \u0438\u043C \u0441\u043A\u0438\u0434\u043E\u0447\u043D\u0443\u044E \u0440\u0430\u0441\u0441\u044B\u043B\u043A\u0443?"), /*#__PURE__*/React.createElement("li", null, "\u0414\u0438\u0437\u0430\u0439\u043D \u043D\u043E\u0433\u0442\u0435\u0439 \u0440\u0430\u0441\u0442\u0451\u0442 +28% \u043F\u043E \u0432\u044B\u0440\u0443\u0447\u043A\u0435 \u2014 \u043F\u043E\u0440\u0430 \u043F\u043E\u0432\u044B\u0448\u0430\u0442\u044C \u0446\u0435\u043D\u0443 \u0438\u043B\u0438 \u043F\u043E\u0434\u043D\u044F\u0442\u044C \u0434\u043E\u043B\u044E \u0432 \u0437\u0430\u043F\u0438\u0441\u044F\u0445."))))));
}
window.Reports = Reports;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Reports.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/Schedule.jsx
try { (() => {
// Schedule — расписание мастеров (week grid by master)
const MASTERS = [{
  name: 'Лена',
  role: 'старший мастер'
}, {
  name: 'Оля',
  role: 'мастер'
}, {
  name: 'Маргарита',
  role: 'мастер · стажёр'
}];
const SCH_DAYS = ['ПН 21', 'ВТ 22', 'СР 23', 'ЧТ 24', 'ПТ 25', 'СБ 26', 'ВС 27'];

// per master, per day: array of slots {hours, status}
//   status: 'work', 'off', 'lunch'
const SCH_DATA = [
// Лена
[{
  start: 9,
  end: 13,
  kind: 'work'
}, {
  start: 13,
  end: 14,
  kind: 'lunch'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 13,
  kind: 'work'
}, {
  start: 13,
  end: 14,
  kind: 'lunch'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 13,
  kind: 'work'
}, {
  start: 13,
  end: 14,
  kind: 'lunch'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 20,
  kind: 'off'
}, {
  start: 10,
  end: 14,
  kind: 'work'
}, {
  start: 14,
  end: 15,
  kind: 'lunch'
}, {
  start: 15,
  end: 21,
  kind: 'work'
}, {
  start: 10,
  end: 18,
  kind: 'work'
}, {
  start: 9,
  end: 20,
  kind: 'off'
}],
// Оля
[{
  start: 9,
  end: 20,
  kind: 'off'
}, {
  start: 10,
  end: 14,
  kind: 'work'
}, {
  start: 14,
  end: 15,
  kind: 'lunch'
}, {
  start: 15,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 13,
  kind: 'work'
}, {
  start: 13,
  end: 14,
  kind: 'lunch'
}, {
  start: 14,
  end: 18,
  kind: 'work'
}, {
  start: 10,
  end: 18,
  kind: 'work'
}, {
  start: 11,
  end: 15,
  kind: 'work'
}, {
  start: 15,
  end: 16,
  kind: 'lunch'
}, {
  start: 16,
  end: 21,
  kind: 'work'
}, {
  start: 10,
  end: 20,
  kind: 'work'
}, {
  start: 11,
  end: 17,
  kind: 'work'
}],
// Маргарита
[{
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 20,
  kind: 'off'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 14,
  end: 20,
  kind: 'work'
}, {
  start: 9,
  end: 20,
  kind: 'off'
}, {
  start: 9,
  end: 20,
  kind: 'off'
}]];
const SCH_HOURS = 12; // 9–21
function Schedule() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      height: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "cal-toolbar"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0421\u0435\u0433\u043E\u0434\u043D\u044F"), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevL",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    className: "icon-btn"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevR",
    size: 18
  })), /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "21 \u2013 27 \u0430\u043F\u0440\u0435\u043B\u044F 2026"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-secondary btn-sm"
  }, "\u0428\u0430\u0431\u043B\u043E\u043D \u043D\u0435\u0434\u0435\u043B\u0438"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary btn-sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 14
  }), "\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u043C\u0430\u0441\u0442\u0435\u0440\u0430")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0,
      background: '#fff',
      border: '1px solid var(--border-1)',
      borderRadius: 8,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '180px repeat(7,1fr)',
      minWidth: 980
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 14px',
      fontSize: 11,
      textTransform: 'uppercase',
      color: 'var(--fg-3)',
      letterSpacing: '.04em',
      fontWeight: 500,
      borderBottom: '1px solid var(--border-1)',
      borderRight: '1px solid var(--border-1)',
      background: 'var(--bg-panel-2)'
    }
  }, "\u041C\u0430\u0441\u0442\u0435\u0440"), SCH_DAYS.map((d, i) => /*#__PURE__*/React.createElement("div", {
    key: d,
    style: {
      padding: '10px 12px',
      fontSize: 11,
      textTransform: 'uppercase',
      color: i === 2 ? 'var(--accent)' : 'var(--fg-3)',
      letterSpacing: '.04em',
      fontWeight: 500,
      borderBottom: '1px solid var(--border-1)',
      borderRight: i < 6 ? '1px solid var(--border-2)' : '0',
      background: 'var(--bg-panel-2)'
    }
  }, d)), MASTERS.map((m, mi) => {
    const masterDays = [];
    let dayCursor = 0;
    const slotsByDay = [[], [], [], [], [], [], []];
    // re-bucket SCH_DATA[mi] by counting slots per day (split on 'off' or hours reset)
    // Our flat data: walk and infer day breaks by start<= prev end logic; simpler: precomputed per-day
    const flat = SCH_DATA[mi];
    // We'll redistribute manually since data is flat:
    let acc = 0;
    for (const slot of flat) {
      slotsByDay[acc % 7] = slotsByDay[acc % 7] || [];
      slotsByDay[acc % 7].push(slot);
      // advance day when we hit an 'off' single-day or when next slot starts <= current ends
      // Simpler: re-bucket using groups separated by 'off' single entries OR sequence reset
      acc;
    }
    // Real grouping: scan and bump day on slot.start <= previous slot.start
    let day = 0;
    const bucket = [[], [], [], [], [], [], []];
    let prev = null;
    for (const s of flat) {
      if (prev && s.start <= prev.end - 0.01 && !(prev.kind === 'work' && s.kind === 'lunch') && !(prev.kind === 'lunch' && s.kind === 'work')) day++;
      if (prev && s.start < prev.start) day++;
      if (day > 6) day = 6;
      bucket[day].push(s);
      prev = s;
    }
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: mi
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '14px',
        borderBottom: '1px solid var(--border-2)',
        borderRight: '1px solid var(--border-1)',
        display: 'flex',
        gap: 10,
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement(Avatar, {
      name: m.name,
      size: "sm"
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        fontWeight: 600
      }
    }, m.name), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: 'var(--fg-3)'
      }
    }, m.role))), bucket.map((daySlots, di) => /*#__PURE__*/React.createElement("div", {
      key: di,
      style: {
        padding: 8,
        borderBottom: '1px solid var(--border-2)',
        borderRight: di < 6 ? '1px solid var(--border-2)' : '0',
        position: 'relative',
        minHeight: 64
      }
    }, daySlots.map((s, si) => {
      const left = (s.start - 9) / SCH_HOURS * 100;
      const width = (s.end - s.start) / SCH_HOURS * 100;
      const styles = {
        work: {
          background: '#DEF5E5',
          color: '#128640',
          borderColor: '#16A34A'
        },
        lunch: {
          background: '#FFF1C8',
          color: '#B5821A',
          borderColor: '#E0A21A'
        },
        off: {
          background: 'var(--ark-gray-100)',
          color: 'var(--fg-3)',
          borderColor: 'var(--ark-gray-300)'
        }
      }[s.kind];
      return /*#__PURE__*/React.createElement("div", {
        key: si,
        style: {
          position: 'absolute',
          top: 8,
          bottom: 8,
          left: `calc(${left}% + 8px)`,
          width: `calc(${width}% - 4px)`,
          background: styles.background,
          color: styles.color,
          borderLeft: `2px solid ${styles.borderColor}`,
          borderRadius: 4,
          padding: '4px 6px',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          display: 'flex',
          alignItems: 'center',
          overflow: 'hidden',
          whiteSpace: 'nowrap'
        }
      }, s.kind === 'off' ? 'выходной' : `${s.start}:00–${s.end}:00`);
    }))));
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      display: 'flex',
      gap: 18,
      alignItems: 'center',
      fontSize: 12,
      color: 'var(--fg-2)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      background: '#DEF5E5',
      border: '1px solid #16A34A',
      borderRadius: 2
    }
  }), "\u0441\u043C\u0435\u043D\u0430"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      background: '#FFF1C8',
      border: '1px solid #E0A21A',
      borderRadius: 2
    }
  }), "\u043E\u0431\u0435\u0434"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      background: 'var(--ark-gray-100)',
      border: '1px solid var(--ark-gray-300)',
      borderRadius: 2
    }
  }), "\u0432\u044B\u0445\u043E\u0434\u043D\u043E\u0439")));
}
window.Schedule = Schedule;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/Schedule.jsx", error: String((e && e.message) || e) }); }

// ui_kits/crm/components/primitives.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Primitives — small reusable components
const {
  useState
} = React;
const AVATAR_COLORS = ['#E26B7E', '#E08A3C', '#C9A227', '#59A861', '#3FA3B3', '#4F86E0', '#8865D8', '#B85F9E'];
function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = h * 31 + name.charCodeAt(i) | 0;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}
function initials(name) {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
}
function Avatar({
  name,
  size = 'md'
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: `av av-${size}`,
    style: {
      background: avatarColor(name)
    }
  }, initials(name));
}
function Chip({
  kind = 'new',
  children
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: `chip chip-${kind}`
  }, children);
}
const STATUS_LABEL = {
  new: 'Новый',
  contact: 'Контакт',
  qualified: 'Квалиф.',
  won: 'Выигран',
  lost: 'Проигран'
};

// Icons (Lucide-style inline SVG)
const Icon = ({
  name,
  size = 18,
  ...rest
}) => {
  const paths = {
    home: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M3 12 12 4l9 8M5 10v9h14v-9"
    })),
    kanban: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "3",
      y: "4",
      width: "5",
      height: "16",
      rx: "1"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "10",
      y: "4",
      width: "5",
      height: "16",
      rx: "1"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "17",
      y: "4",
      width: "4",
      height: "16",
      rx: "1"
    })),
    chat: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M21 12a8 8 0 1 1-3-6.2L21 5l-1 4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M8 11h8M8 14h5"
    })),
    cal: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "3",
      y: "5",
      width: "18",
      height: "16",
      rx: "2"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M3 9h18M8 3v4M16 3v4"
    })),
    search: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "11",
      cy: "11",
      r: "7"
    }), /*#__PURE__*/React.createElement("path", {
      d: "m20 20-4-4"
    })),
    plus: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M12 5v14M5 12h14"
    })),
    bell: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9z"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M10 21h4"
    })),
    settings: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "3"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M19 12c0-.4 0-.8-.1-1.2l2-1.5-2-3.4-2.3.9c-.6-.5-1.3-.9-2-1.2L14 3h-4l-.6 2.6c-.7.3-1.4.7-2 1.2l-2.3-.9-2 3.4 2 1.5C5 11.2 5 11.6 5 12s0 .8.1 1.2l-2 1.5 2 3.4 2.3-.9c.6.5 1.3.9 2 1.2L10 21h4l.6-2.6c.7-.3 1.4-.7 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"
    })),
    paperclip: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M21 11.5 12.5 20a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"
    })),
    smile: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M9 14a4 4 0 0 0 6 0M9 9h.01M15 9h.01"
    })),
    mic: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "9",
      y: "3",
      width: "6",
      height: "12",
      rx: "3"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 11a7 7 0 0 0 14 0M12 18v3"
    })),
    send: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "m3 11 18-8-8 18-2-8-8-2z"
    })),
    sparkle: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "3"
    })),
    chevL: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M15 6l-6 6 6 6"
    })),
    chevR: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M9 6l6 6-6 6"
    })),
    more: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "5",
      cy: "12",
      r: "1.5"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "1.5"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "19",
      cy: "12",
      r: "1.5"
    })),
    phone: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"
    })),
    filter: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M3 5h18l-7 9v6l-4-2v-4z"
    })),
    user: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "8",
      r: "4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M4 21a8 8 0 0 1 16 0"
    })),
    clock: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M12 7v5l3 2"
    })),
    chart: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M3 3v18h18"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M7 14l4-4 3 3 5-7"
    })),
    card: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "3",
      y: "6",
      width: "18",
      height: "13",
      rx: "2"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M3 10h18M7 15h4"
    }))
  };
  return /*#__PURE__*/React.createElement("svg", _extends({
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, rest), paths[name]);
};
Object.assign(window, {
  Avatar,
  Chip,
  Icon,
  STATUS_LABEL,
  avatarColor,
  initials
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/crm/components/primitives.jsx", error: String((e && e.message) || e) }); }

})();
