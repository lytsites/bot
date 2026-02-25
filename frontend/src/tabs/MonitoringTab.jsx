import React from 'react'
import Sidebar from '../components/Sidebar'
import MonitoringListeningHistory from '../sideTabs/MonitoringListeningHistory'
import HomeAutoChatHistory from '../sideTabs/HomeAutoChatHistory'
import HomeRequisitesHistory from '../sideTabs/HomeRequisitesHistory'
import MonitoringAdminAccounts from '../sideTabs/MonitoringAdminAccounts'
import MonitoringAdminWorkers from '../sideTabs/MonitoringAdminWorkers'
import MonitoringAdminErrors from '../sideTabs/MonitoringAdminErrors'

export default function MonitoringTab({
  isAdmin,
  isSuperAdmin,
  activeSideTab,
  setActiveSideTab,
  listeningHistoryProps,
  autoChatHistoryProps,
  requisitesHistoryProps,
  adminAccountsProps,
  adminWorkersProps,
  adminErrorsProps,
  canGroupReading = true,
  canAutoDialogs = true,
}) {
  const items = []
  if (canGroupReading) items.push({ id: 'listening_history', label: 'История чтения групп' })
  if (canAutoDialogs) items.push({ id: 'auto_history', label: 'История авто. диалогов' })
  items.push({ id: 'requisites_history', label: 'История реквизитов' })

  if (isAdmin) {
    items.push(
      { id: 'admin-accounts', label: 'Аккаунты' },
      { id: 'admin-workers', label: 'История воркеров' }
    )
  }
  if (isSuperAdmin) {
    items.push({ id: 'admin-errors', label: 'Инциденты' })
  }

  return (
    <div className="workspace">
      <Sidebar title="Мониторинг" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'listening_history' && canGroupReading && <MonitoringListeningHistory {...listeningHistoryProps} />}
        {activeSideTab === 'auto_history' && canAutoDialogs && <HomeAutoChatHistory {...autoChatHistoryProps} />}
        {activeSideTab === 'requisites_history' && <HomeRequisitesHistory {...requisitesHistoryProps} />}
        {activeSideTab === 'admin-accounts' && isAdmin && (
          <MonitoringAdminAccounts {...adminAccountsProps} />
        )}
        {activeSideTab === 'admin-workers' && isAdmin && (
          <MonitoringAdminWorkers {...adminWorkersProps} />
        )}
        {activeSideTab === 'admin-errors' && isSuperAdmin && (
          <MonitoringAdminErrors {...adminErrorsProps} />
        )}
      </div>
    </div>
  )
}
