"use client"

import { useState, useMemo } from "react"
import { Atom, LayoutDashboard, Grid3X3, Terminal as TerminalIcon, Wifi, WifiOff, Wrench } from "lucide-react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { DashboardTab } from "@/components/tabs/dashboard-tab"
import { AppsTab } from "@/components/tabs/apps-tab"
import { TerminalTab } from "@/components/tabs/terminal-tab"
import { ToolsTab } from "@/components/tabs/tools-tab"
import { useApiSimulation } from "@/hooks/use-api-simulation"
import { cn } from "@/lib/utils"

export default function UniverseOS() {
  const {
    mounted,
    isRunning,
    isConnected,
    error,
    units,
    pulses,
    chartData,
    totalEnergy,
    totalPulses,
    createUnit,
    sendPulse,
    togglePause,
    executeCommand
  } = useApiSimulation()

  const [startTime] = useState(() => new Date())

  const connectionStatus = useMemo(() => {
    if (isConnected) {
      return {
        icon: Wifi,
        text: "API Conectada",
        className: "text-green-400 border-green-500/30 bg-green-500/10"
      }
    }
    return {
      icon: WifiOff,
      text: error || "Desconectado",
      className: "text-red-400 border-red-500/30 bg-red-500/10"
    }
  }, [isConnected, error])

  if (!mounted) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-neon-blue/30 border-t-neon-blue" />
          <p className="text-muted-foreground text-sm">Conectando ao servidor...</p>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-background">
      {/* Background gradient effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-neon-blue/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-neon-purple/5 rounded-full blur-[150px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-neon-cyan/3 rounded-full blur-[200px]" />
      </div>

      <div className="relative z-10 container mx-auto px-4 py-6">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-neon-blue/20 border border-neon-blue/30">
                <Atom className="h-5 w-5 text-neon-blue" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">Universe OS</h1>
                <p className="text-xs text-muted-foreground">Sistema de Simulação v2.0</p>
              </div>
            </div>

            {/* Connection Status */}
            <div className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium",
              connectionStatus.className
            )}>
              <connectionStatus.icon className="h-3.5 w-3.5" />
              <span>{connectionStatus.text}</span>
            </div>
          </div>
        </header>

        {/* Main Tabs */}
        <Tabs defaultValue="dashboard" className="w-full">
          <TabsList className="mb-6 bg-secondary/50 border border-border/50 p-1">
            <TabsTrigger 
              value="dashboard" 
              className="gap-2 data-[state=active]:bg-neon-blue/20 data-[state=active]:text-neon-blue data-[state=active]:border-neon-blue/30"
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger 
              value="apps"
              className="gap-2 data-[state=active]:bg-neon-purple/20 data-[state=active]:text-neon-purple data-[state=active]:border-neon-purple/30"
            >
              <Grid3X3 className="h-4 w-4" />
              Apps
            </TabsTrigger>
            <TabsTrigger 
              value="terminal"
              className="gap-2 data-[state=active]:bg-neon-cyan/20 data-[state=active]:text-neon-cyan data-[state=active]:border-neon-cyan/30"
            >
              <TerminalIcon className="h-4 w-4" />
              Terminal
            </TabsTrigger>
            <TabsTrigger 
              value="tools"
              className="gap-2 data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400 data-[state=active]:border-amber-500/30"
            >
              <Wrench className="h-4 w-4" />
              Ferramentas
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="mt-0">
            <DashboardTab
              isRunning={isRunning}
              units={units}
              pulses={pulses}
              chartData={chartData}
              totalEnergy={totalEnergy}
              totalPulses={totalPulses}
              onCreateUnit={createUnit}
              onSendPulse={sendPulse}
              onTogglePause={togglePause}

              
            />
          </TabsContent>

          <TabsContent value="apps" className="mt-0">
            <AppsTab
              isConnected={isConnected}
              isRunning={isRunning}
              units={units}
              pulses={pulses}
              totalEnergy={totalEnergy}
              startTime={startTime}
              onTogglePause={togglePause}
              onCreateUnit={createUnit}
              onSendPulse={sendPulse}
            />
          </TabsContent>

          <TabsContent value="terminal" className="mt-0">
            <TerminalTab
              isConnected={isConnected}
              onExecuteCommand={executeCommand}
            />
          </TabsContent>

          <TabsContent value="tools" className="mt-0">
            <ToolsTab
              units={units}
              pulses={pulses}
              totalEnergy={totalEnergy}
              executeCommand={executeCommand}
            />
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <footer className="text-center text-xs text-muted-foreground py-4 mt-6 border-t border-border/30">
          <p>Universe OS • Sistema de Simulação Autônoma</p>
        </footer>
      </div>
    </main>
  )
}
