import React from 'react'
import Sidebar from '../components/Sidebar'
import SettingsMain from '../sideTabs/SettingsMain'
import SettingsAccounts from '../sideTabs/SettingsAccounts'
import SettingsListening from '../sideTabs/SettingsListening'
import SettingsAutoChat from '../sideTabs/SettingsAutoChat'
import SettingsServiceControl from '../sideTabs/SettingsServiceControl'

export default function SettingsTab({
  activeSideTab,
  setActiveSideTab,
  accountsProps,
  listeningProps,
  autoChatProps,
  serviceControlProps,
  themeProps,
  canGroupReading = true,
  canAutoDialogs = true,
  canServiceControl = false,
}) {
  const items = [
    { id: 'main', label: 'Основные' },
    { id: 'accounts', label: 'Аккаунты' },
  ]
  if (canGroupReading) items.push({ id: 'listening', label: 'Чтение групп' })
  if (canAutoDialogs) items.push({ id: 'auto', label: 'Авто. диалоги' })
  if (canServiceControl) items.push({ id: 'service-control', label: 'Сервисы' })

  return (
    <div className="workspace">
      <Sidebar title="Настройки" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'main' && <SettingsMain {...themeProps} />}
        {activeSideTab === 'accounts' && <SettingsAccounts {...accountsProps} />}
        {activeSideTab === 'listening' && canGroupReading && <SettingsListening {...listeningProps} />}
        {activeSideTab === 'auto' && canAutoDialogs && <SettingsAutoChat {...autoChatProps} />}
        {activeSideTab === 'service-control' && canServiceControl && <SettingsServiceControl {...serviceControlProps} />}
      </div>
    </div>
  )
}
