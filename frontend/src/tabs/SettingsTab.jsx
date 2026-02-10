import React from 'react'
import Sidebar from '../components/Sidebar'
import SettingsMain from '../sideTabs/SettingsMain'
import SettingsAccounts from '../sideTabs/SettingsAccounts'
import SettingsListening from '../sideTabs/SettingsListening'
import SettingsAutoChat from '../sideTabs/SettingsAutoChat'

export default function SettingsTab({
  activeSideTab,
  setActiveSideTab,
  accountsProps,
  listeningProps,
  autoChatProps,
  themeProps,
  canGroupReading = true,
  canAutoDialogs = true,
  }) {
  const items = [
    { id: 'main', label: 'Основные' },
    { id: 'accounts', label: 'Аккаунты' },
  ]
  if (canGroupReading) items.push({ id: 'listening', label: 'Чтение групп' })
  if (canAutoDialogs) items.push({ id: 'auto', label: 'Авто. диалоги' })

  return (
    <div className="workspace">
      <Sidebar title="Настройки" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'main' && <SettingsMain {...themeProps} />}
        {activeSideTab === 'accounts' && <SettingsAccounts {...accountsProps} />}
        {activeSideTab === 'listening' && canGroupReading && <SettingsListening {...listeningProps} />}
        {activeSideTab === 'auto' && canAutoDialogs && <SettingsAutoChat {...autoChatProps} />}
      </div>
    </div>
  )
}
