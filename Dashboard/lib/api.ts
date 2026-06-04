// Dashboard/lib/api.ts

// ⭐ Detecta dinamicamente o IP do servidor
export const API_BASE_URL = (() => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Se estiver acessando por IP (não localhost)
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      // Usa o mesmo IP da URL atual, mas na porta 8000
      return `http://${hostname}:8000`;
    }
  }
  
  // Fallback para desenvolvimento local
  // ⭐ ALTERE PARA O SEU IP FIXO
  return 'http://192.168.0.26:8000';
})();

console.log('🔧 API_BASE_URL:', API_BASE_URL);