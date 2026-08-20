/**
 * 安全AI项目API客户端
 * 封装所有REST API调用
 */

export interface APIError {
  message: string;
  code?: string;
  status?: number;
}

export interface Alert {
  id: string;
  level: 'low' | 'medium' | 'high' | 'critical';
  type: string;
  message: string;
  unitId?: string;
  vehicleId?: string;
  driverId?: string;
  timestamp: string;
  [key: string]: unknown;
}

export interface VehicleRealtime {
  id: string;
  gps: {
    lat: number;
    lng: number;
    speed: number;
    heading: number;
    timestamp: string;
  };
  can?: {
    speed?: number;
    rpm?: number;
    temperature?: number;
    fuel?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface HeatmapData {
  type: 'area' | 'segment';
  data: Array<{
    id: string;
    coordinates: Array<[number, number]>;
    risk_level: number;
    count?: number;
    [key: string]: unknown;
  }>;
  window: string;
}

export interface DriverFeatures {
  id: string;
  name: string;
  features: {
    behavior_score?: number;
    risk_score?: number;
    violations?: number;
    accidents?: number;
    [key: string]: unknown;
  };
  window: string;
  [key: string]: unknown;
}

export interface Intervention {
  id?: string;
  type: string;
  target: {
    type: 'driver' | 'vehicle' | 'route';
    id: string;
  };
  action: string;
  assignee?: string;
  priority?: 'low' | 'medium' | 'high';
  [key: string]: unknown;
}

export interface AIReport {
  id: string;
  type: 'driver' | 'vehicle' | 'route';
  target_id: string;
  risk_profile: {
    score: number;
    level: string;
    factors: Array<{ name: string; weight: number; [key: string]: unknown }>;
    [key: string]: unknown;
  };
  behavior_analysis?: Record<string, unknown>;
  suggestions?: Array<{ priority: string; action: string; [key: string]: unknown }>;
  generated_at: string;
  [key: string]: unknown;
}

export class APIClient {
  private baseUrl: string;
  private apiKey?: string;
  private token?: string;

  constructor(config: {
    baseUrl: string;
    apiKey?: string;
    token?: string;
  }) {
    this.baseUrl = config.baseUrl.replace(/\/$/, ''); // 移除尾部斜杠
    this.apiKey = config.apiKey;
    this.token = config.token;
  }

  private async request<T>(
    method: string,
    path: string,
    params?: Record<string, unknown>,
    body?: unknown
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    
    // 添加查询参数
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'Accept': 'application/vnd.bus.v1+json', // API版本控制
    };

    // 添加认证头
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const options: RequestInit = {
      method,
      headers,
    };

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url.toString(), options);
      
      if (!response.ok) {
        const errorText = await response.text();
        let errorData: APIError;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { message: errorText };
        }
        errorData.status = response.status;
        throw errorData;
      }

      const data = await response.json();
      return data as T;
    } catch (error) {
      if (error && typeof error === 'object' && 'status' in error) {
        throw error;
      }
      throw {
        message: error instanceof Error ? error.message : '网络请求失败',
        code: 'NETWORK_ERROR',
      } as APIError;
    }
  }

  /**
   * 获取实时预警清单
   * GET /api/alerts?level=&unitId=&window=4h
   */
  async getAlerts(params?: {
    level?: 'low' | 'medium' | 'high' | 'critical';
    unitId?: string;
    window?: string;
  }): Promise<{ alerts: Alert[]; total: number }> {
    return this.request<{ alerts: Alert[]; total: number }>('GET', '/api/alerts', params);
  }

  /**
   * 获取车辆实时工况和GPS数据
   * GET /api/vehicles/{id}/realtime
   */
  async getVehicleRealtime(id: string): Promise<VehicleRealtime> {
    return this.request<VehicleRealtime>('GET', `/api/vehicles/${id}/realtime`);
  }

  /**
   * 获取区域或路段热力图数据
   * GET /api/heatmap?type=area|segment&window=4h
   */
  async getHeatmap(params: {
    type: 'area' | 'segment';
    window?: string;
  }): Promise<HeatmapData> {
    return this.request<HeatmapData>('GET', '/api/heatmap', params);
  }

  /**
   * 获取驾驶员特征数据
   * GET /api/features/driver/{id}?window=30d
   */
  async getDriverFeatures(id: string, params?: { window?: string }): Promise<DriverFeatures> {
    return this.request<DriverFeatures>('GET', `/api/features/driver/${id}`, params);
  }

  /**
   * 新建干预并指派
   * POST /api/interventions
   */
  async createIntervention(intervention: Intervention): Promise<{ id: string; [key: string]: unknown }> {
    return this.request<{ id: string; [key: string]: unknown }>('POST', '/api/interventions', undefined, intervention);
  }

  /**
   * 获取AI智能报告
   * GET /api/reports/ai/driver/{id}
   */
  async getAIReport(type: 'driver' | 'vehicle' | 'route', id: string): Promise<AIReport> {
    return this.request<AIReport>('GET', `/api/reports/ai/${type}/${id}`);
  }
}

