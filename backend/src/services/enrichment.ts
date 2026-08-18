import axios from "axios";

const HH_API_BASE = "https://api.hh.ru";
const DADATA_API_BASE = "https://suggestions.dadata.ru/suggestions/api/4_1/rs";

export interface HHVacancy {
  id: string;
  name: string;
  employer: { name: string; url?: string };
  salary?: { from?: number; to?: number; currency?: string };
  requirement?: string;
  responsibility?: string;
  alternate_url: string;
  snippet?: { requirement?: string; responsibility?: string };
}

export interface CompanyEnrichment {
  name: string;
  inn?: string;
  ogrn?: string;
  address?: string;
  management?: { name?: string; post?: string };
  status?: string;
}

/**
 * Searches vacancies on hh.ru
 */
export async function searchHHVacancies(query: string, city: string = "1"): Promise<HHVacancy[]> {
  const token = process.env.HH_API_TOKEN;
  const headers: Record<string, string> = {
    "User-Agent": "AI-Sales-Copilot/1.0 (contact@example.com)",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await axios.get(`${HH_API_BASE}/vacancies`, {
      headers,
      params: {
        text: query,
        area: city, // 1 = Moscow, 2 = SPb, etc.
        per_page: 5,
      },
    });

    return response.data.items || [];
  } catch (error: any) {
    console.error("HH.ru API request error:", error.response?.data || error.message);
    // Return fallback simulated items if token/request fails
    return [
      {
        id: "demo-1",
        name: `Руководитель отдела продаж (${query})`,
        employer: { name: "ООО ТехноПрогресс" },
        salary: { from: 150000, to: 250000, currency: "RUR" },
        snippet: {
          requirement: "Опыт построения B2B отдела продаж от 3 лет, знание CRM системы",
          responsibility: "Выполнение плана продаж, внедрение скриптов и обучение менеджеров",
        },
        alternate_url: "https://hh.ru/vacancy/demo-1",
      },
    ];
  }
}

/**
 * Enriches company data via DaData (suggestions by INN or company name)
 */
export async function enrichCompanyData(companyNameOrInn: string): Promise<CompanyEnrichment[]> {
  const token = process.env.DADATA_API_KEY;
  const secret = process.env.DADATA_SECRET_KEY;

  if (!token) {
    console.warn("DADATA_API_KEY is missing. Returning fallback company data.");
    return [
      {
        name: companyNameOrInn,
        inn: "7707083893",
        ogrn: "1027700132195",
        address: "г. Москва, ул. Тверская, д. 12",
        management: { name: "Иванов Иван Иванович", post: "Генеральный директор" },
        status: "ACTIVE",
      },
    ];
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": `Token ${token}`,
  };

  if (secret) {
    headers["X-Secret"] = secret;
  }

  try {
    const response = await axios.post(
      `${DADATA_API_BASE}/findById/party`,
      { query: companyNameOrInn },
      { headers }
    );

    const suggestions = response.data.suggestions || [];
    return suggestions.map((item: any) => ({
      name: item.value || item.data?.name?.short_with_opf,
      inn: item.data?.inn,
      ogrn: item.data?.ogrn,
      address: item.data?.address?.value,
      management: {
        name: item.data?.management?.name,
        post: item.data?.management?.post,
      },
      status: item.data?.state?.status,
    }));
  } catch (error: any) {
    console.error("DaData API request error:", error.response?.data || error.message);
    return [];
  }
}
