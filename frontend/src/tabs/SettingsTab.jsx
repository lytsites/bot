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
}) {
  const items = [
    { id: 'main', label: 'Основные' },
    { id: 'accounts', label: 'Аккаунты' },
    { id: 'listening', label: 'Прослушивание' },
    { id: 'auto', label: 'Авто. общение' },
  ]

  return (
    <div className="workspace">
      <Sidebar title="Настройки" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'main' && <SettingsMain {...themeProps} />}
        {activeSideTab === 'accounts' && <SettingsAccounts {...accountsProps} />}
        {activeSideTab === 'listening' && <SettingsListening {...listeningProps} />}
        {activeSideTab === 'auto' && <SettingsAutoChat {...autoChatProps} />}
      </div>
    </div>
  )
}
