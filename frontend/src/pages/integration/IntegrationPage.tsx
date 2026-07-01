import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate, formatTime } from '@/lib/format';
import {
  useIntegrationOverview,
  useMnoSyncStatus,
  useRunningAllJob,
} from '@/api/hooks/integration';
import { useSyncRegions, useStartMnoSync, useStartMnoSyncAll } from '@/api/mutations/integration';
import { useFederalDistricts } from '@/api/hooks/regions';
import type { ApiError, MnoSyncJob } from '@/api/aliases';
import './IntegrationPage.css';

/** Спец-значение селектора региона: синхронизировать МНО по ВСЕМ регионам справочника. */
const ALL_REGIONS = '__all__';

/**
 * Раздел «Интеграция ФГИС» — доступен ТОЛЬКО супер-админу (гард в App.tsx + пункт меню).
 * Живой источник: ФГИС УТКО (public-api.utko.mnr.gov.ru), слой 5 — места накопления ТКО.
 * Две панели действий (регионы / МНО) + сводная таблица per_region.
 */

/** «ДД.ММ.ГГГГ ЧЧ:ММ» или «—» для пустого/невалидного ISO. */
function fmtDateTime(iso: string | null | undefined): string {
  const d = formatDate(iso);
  return d ? `${d} ${formatTime(iso)}` : '—';
}

/** Достаёт текст message из конверта ошибки API ({error:{message}}), иначе пустая строка. */
function apiErrorMessage(e: unknown): string {
  if (e && typeof e === 'object' && 'error' in e) {
    const msg = (e as ApiError).error?.message;
    if (msg) return msg;
  }
  return '';
}

export function IntegrationPage() {
  const qc = useQueryClient();
  const { message, showToast } = useToast();

  const overviewQuery = useIntegrationOverview();
  const districtsQuery = useFederalDistricts();

  const syncRegions = useSyncRegions();
  const startMno = useStartMnoSync();
  const startMnoAll = useStartMnoSyncAll();

  // Выбранный регион и активная фоновая задача синхронизации МНО.
  const [mnoRegion, setMnoRegion] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  // Инлайн-итог синхронизации регионов («создано X, обновлено Y»).
  const [regionsSummary, setRegionsSummary] = useState<string | null>(null);
  // Чтобы обработать завершение задачи ровно один раз (инвалидация + тост).
  const handledJobRef = useRef<string | null>(null);

  const statusQuery = useMnoSyncStatus(jobId);
  const status = statusQuery.data;

  // Переподключение к идущей фоновой задаче «Все регионы» после перезагрузки (F5).
  // Бэк-задача серверная и НЕ прерывается — теряется лишь job_id во фронт-состоянии.
  const runningAllQuery = useRunningAllJob();

  const overview = overviewQuery.data;
  const perRegion = useMemo(() => overview?.per_region ?? [], [overview]);

  // Карта id округа → краткий код («ЦФО»…) для колонки «Округ».
  const fedLabel = useMemo(() => {
    const map = new Map<number, string>();
    for (const d of districtsQuery.data ?? []) map.set(d.id, d.code);
    return (id: number) => map.get(id) ?? '—';
  }, [districtsQuery.data]);

  const isRunning =
    status?.state === 'running' || startMno.isPending || startMnoAll.isPending;

  // Прогресс одиночного региона: доля загруженных деталей от обнаруженного.
  const pct =
    status && status.discovered > 0
      ? Math.min(100, Math.round((status.fetched / status.discovered) * 100))
      : null;

  // Прогресс «все регионы»: доля пройденных субъектов от общего числа.
  const allPct =
    status && status.regions_total > 0
      ? Math.min(100, Math.round((status.regions_done / status.regions_total) * 100))
      : null;

  // Обработка завершения фоновой задачи: один раз на job_id → инвалидация + итог.
  useEffect(() => {
    if (!jobId || !status || status.state === 'running') return;
    if (handledJobRef.current === jobId) return;
    handledJobRef.current = jobId;
    qc.invalidateQueries({ queryKey: ['integration', 'overview'] });
    qc.invalidateQueries({ queryKey: ['mno'] });
    if (status.state === 'done') {
      const failed =
        status.scope === 'all' && status.regions_failed > 0
          ? `, с ошибками ${status.regions_failed}`
          : '';
      const scope =
        status.scope === 'all'
          ? `все регионы (${status.regions_done}/${status.regions_total}${failed})`
          : status.region_name;
      showToast(`Синхронизация МНО завершена: ${scope} — записано ${status.upserted}.`);
    } else {
      showToast(`Ошибка синхронизации МНО: ${status.error || 'неизвестная ошибка'}`);
    }
  }, [jobId, status, qc, showToast]);

  // Переподключение к идущей задаче «Все регионы» после F5: если ручная задача не активна
  // (jobId пуст) и на сервере есть ИДУЩАЯ фоновая синхронизация — подхватываем её job_id и
  // выставляем селектор в ALL_REGIONS, чтобы опрос useMnoSyncStatus(jobId) продолжил прогресс.
  // Уже завершённую задачу (done/error) НЕ подхватываем — только running.
  useEffect(() => {
    const running = runningAllQuery.data;
    if (jobId != null || !running || running.state !== 'running') return;
    setJobId(running.job_id);
    setMnoRegion(ALL_REGIONS);
  }, [runningAllQuery.data, jobId]);

  const handleSyncRegions = () => {
    if (syncRegions.isPending) return;
    syncRegions.mutate(undefined, {
      onSuccess: (res) => {
        setRegionsSummary(`создано ${res.created}, обновлено ${res.updated}`);
        showToast(
          `Регионы синхронизированы: всего ${res.total}, создано ${res.created}, обновлено ${res.updated}.`
        );
      },
      onError: (e) => showToast(apiErrorMessage(e) || 'Не удалось синхронизировать регионы.'),
    });
  };

  const handleSyncMno = () => {
    if (isRunning) return;
    if (!mnoRegion) {
      showToast('Выберите регион для синхронизации МНО.');
      return;
    }
    // Разрешаем повторную обработку завершения для новой задачи.
    handledJobRef.current = null;
    const onSuccess = (job: MnoSyncJob) => setJobId(job.job_id);
    const onError = (e: unknown) =>
      showToast(apiErrorMessage(e) || 'Не удалось запустить синхронизацию МНО.');
    // «Все регионы» → одна фоновая задача по всему справочнику; иначе — один регион.
    if (mnoRegion === ALL_REGIONS) {
      startMnoAll.mutate(undefined, { onSuccess, onError });
    } else {
      startMno.mutate(mnoRegion, { onSuccess, onError });
    }
  };

  const regionsTotal = overview ? overview.regions.total : null;
  const mnoTotal = overview ? overview.mno.total : null;

  const stateLabel =
    status?.state === 'done'
      ? 'Завершено'
      : status?.state === 'error'
        ? 'Ошибка'
        : 'Идёт синхронизация';

  return (
    <div className="de-intg-wrap">
      {/* Шапка */}
      <div className="de-intg-header">
        <div className="de-intg-head-text">
          <h1 className="de-intg-title">Интеграция ФГИС</h1>
          <div className="de-intg-subtitle">
            Источник: ФГИС УТКО (public-api.utko.mnr.gov.ru), слой 5 — места накопления ТКО
          </div>
        </div>
      </div>

      <div className="de-intg-content">
        {/* Панели действий */}
        <div className="de-intg-panels">
          {/* Регионы */}
          <section className="de-intg-panel">
            <div className="de-intg-panel-head">
              <span className="de-intg-panel-icon">
                <Icon name="map" size={16} />
              </span>
              <div style={{ minWidth: 0 }}>
                <h2 className="de-intg-panel-title">Регионы (субъекты РФ)</h2>
                <div className="de-intg-panel-sub">Справочник субъектов и федеральных округов</div>
              </div>
            </div>
            <div className="de-intg-panel-body">
              <div className="de-intg-metrics">
                <div className="de-intg-metric">
                  <div className="de-intg-metric-num">{regionsTotal ?? '—'}</div>
                  <div className="de-intg-metric-label">субъектов в базе</div>
                </div>
                <div className="de-intg-metric">
                  <div className="de-intg-metric-num mono">
                    {overview ? fmtDateTime(overview.regions.last_sync) : '—'}
                  </div>
                  <div className="de-intg-metric-label">последняя синхронизация</div>
                </div>
              </div>
              <button
                type="button"
                className="de-intg-btn de-intg-btn-primary"
                onClick={handleSyncRegions}
                disabled={syncRegions.isPending}
              >
                <Icon
                  name="refresh-cw"
                  size={15}
                  className={syncRegions.isPending ? 'de-spin' : ''}
                />
                {syncRegions.isPending ? 'Синхронизация…' : 'Синхронизировать регионы'}
              </button>
              {regionsSummary && (
                <div className="de-intg-summary">
                  <Icon name="check" size={14} />
                  Готово: {regionsSummary}
                </div>
              )}
            </div>
          </section>

          {/* МНО */}
          <section className="de-intg-panel">
            <div className="de-intg-panel-head">
              <span className="de-intg-panel-icon">
                <Icon name="pin" size={16} />
              </span>
              <div style={{ minWidth: 0 }}>
                <h2 className="de-intg-panel-title">Места накопления (МНО)</h2>
                <div className="de-intg-panel-sub">Краулер карты ФГИС по региону, слой 5</div>
              </div>
            </div>
            <div className="de-intg-panel-body">
              <div className="de-intg-metrics">
                <div className="de-intg-metric">
                  <div className="de-intg-metric-num">{mnoTotal ?? '—'}</div>
                  <div className="de-intg-metric-label">МНО в базе</div>
                </div>
              </div>

              <div className="de-intg-field">
                <label className="de-intg-label" htmlFor="de-intg-region-select">
                  Регион
                </label>
                <div className="de-intg-inline">
                  <select
                    id="de-intg-region-select"
                    className="de-intg-select"
                    value={mnoRegion}
                    onChange={(e) => setMnoRegion(e.target.value)}
                    disabled={isRunning || perRegion.length === 0}
                  >
                    <option value="">Выберите регион…</option>
                    <option value={ALL_REGIONS}>Все регионы (весь справочник)</option>
                    {perRegion.map((r) => (
                      <option key={r.code} value={r.code}>
                        {r.code} · {r.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="de-intg-btn de-intg-btn-primary"
                    onClick={handleSyncMno}
                    disabled={isRunning || !mnoRegion}
                  >
                    <Icon name="refresh-cw" size={15} className={isRunning ? 'de-spin' : ''} />
                    {isRunning ? 'Синхронизация…' : 'Синхронизировать'}
                  </button>
                </div>
              </div>

              {perRegion.length === 0 && !overviewQuery.isLoading && (
                <div className="de-intg-hint">
                  Сначала синхронизируйте регионы — затем выберите регион для загрузки МНО.
                </div>
              )}

              <div className="de-intg-hint">
                <Icon name="alert-circle" size={13} /> Обновление страницы (F5) не прерывает
                синхронизацию — она идёт на сервере.
              </div>

              {/* Прогресс фоновой задачи */}
              {jobId && status && (
                <div className="de-intg-progress">
                  <div className="de-intg-progress-head">
                    <span className={`de-intg-state de-intg-state-${status.state}`}>
                      {status.state === 'running' && (
                        <Icon name="refresh-cw" size={13} className="de-spin" />
                      )}
                      {stateLabel}
                    </span>
                    <span className="de-intg-progress-region">{status.region_name}</span>
                  </div>
                  {status.scope === 'all' ? (
                    <>
                      {/* Порегионный прогресс: доля пройденных субъектов */}
                      {allPct != null && (
                        <div className="de-intg-bar">
                          <div className="de-intg-bar-fill" style={{ width: `${allPct}%` }} />
                        </div>
                      )}
                      <div className="de-intg-region-prog">
                        Регион <span className="de-intg-num">{status.regions_done}</span>
                        <span className="de-intg-num">/{status.regions_total}</span>
                        {status.current_region && (
                          <>
                            {': '}
                            <span className="de-intg-cur">{status.current_region}</span>
                          </>
                        )}
                      </div>
                    </>
                  ) : (
                    pct != null && (
                      <div className="de-intg-bar">
                        <div className="de-intg-bar-fill" style={{ width: `${pct}%` }} />
                      </div>
                    )
                  )}
                  {/* Накопительные счётчики (одиночный регион и «все») */}
                  <div className="de-intg-counters">
                    <span>
                      обнаружено <b>{status.discovered}</b>
                    </span>
                    <span className="de-intg-counters-sep">·</span>
                    <span>
                      детали <b>{status.fetched}</b>
                    </span>
                    <span className="de-intg-counters-sep">·</span>
                    <span>
                      записано <b>{status.upserted}</b>
                    </span>
                  </div>
                  {status.scope === 'all' && status.regions_failed > 0 && (
                    <div className="de-intg-failed">
                      с ошибками: <b>{status.regions_failed}</b>
                    </div>
                  )}
                  {status.state === 'error' && status.error && (
                    <div className="de-intg-progress-error">{status.error}</div>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>

        {/* Сводная таблица по регионам */}
        <div className="de-intg-table-block">
          <div className="de-intg-block-head">
            <h2 className="de-intg-block-title">Регионы в базе</h2>
            <span className="de-intg-block-sub">{perRegion.length} субъектов</span>
          </div>

          {overviewQuery.isLoading ? (
            <div className="de-intg-state-msg">Загрузка…</div>
          ) : overviewQuery.isError ? (
            <div className="de-intg-state-msg error">Не удалось загрузить сводку интеграции.</div>
          ) : perRegion.length === 0 ? (
            <div className="de-intg-state-msg">
              Регионы ещё не синхронизированы. Нажмите «Синхронизировать регионы».
            </div>
          ) : (
            <div className="de-intg-table">
              <div className="de-intg-thead">
                <div className="de-intg-th de-intg-c-region">Регион</div>
                <div className="de-intg-th de-intg-c-fed">Округ</div>
                <div className="de-intg-th de-intg-c-mno">МНО в базе</div>
                <div className="de-intg-th de-intg-c-sync">Посл. синхронизация</div>
              </div>
              {perRegion.map((r) => (
                <div key={r.code} className="de-intg-row">
                  <div className="de-intg-cell de-intg-c-region">
                    <span className="de-intg-code">{r.code}</span>
                    <span className="de-intg-region-name" title={r.name}>
                      {r.name}
                    </span>
                  </div>
                  <div className="de-intg-cell de-intg-c-fed">{fedLabel(r.fed)}</div>
                  <div className="de-intg-cell de-intg-c-mno">{r.mno_count}</div>
                  <div className="de-intg-cell de-intg-c-sync">{fmtDateTime(r.last_sync)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Toast message={message} />
    </div>
  );
}
