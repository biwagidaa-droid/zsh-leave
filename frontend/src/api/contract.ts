import type { ClientPolicy } from "../lib/clientPolicy";
import type {
  Attachment, AuditRow, Balance, BradfordNote, CalendarEvent, Comment, Company, ContractPeriod,
  CoverageRow, Department, Employee, Entitlement, Holiday, ImportPreview, JobRow,
  LeaveRequest, LeaveType, NotificationItem, Page, ReportSummary, SettingItem, User,
} from "./types";

export type RequestFilters = {
  page?: number;
  status?: string;
  q?: string;
  mine?: boolean;
  team?: boolean;
};

export type LeaveDraft = {
  leaveTypeKey: string;
  start: string;
  end: string;
  workingDays: string;
  reason: string;
  replacementId?: number | null;
  employeeId?: number;
  durationKind?: "daily" | "hourly";
  startTime?: string;
  endTime?: string;
  durationMinutes?: number;
};

export interface Api {
  login(username: string, password: string): Promise<User>;
  logout(): Promise<void>;
  me(): Promise<User>;
  changePassword(current: string, next: string): Promise<void>;
  listTypes(): Promise<LeaveType[]>;
  saveType(t: Partial<LeaveType> & { key: string; labelFa: string }): Promise<LeaveType>;
  listRequests(f: RequestFilters): Promise<Page<LeaveRequest>>;
  getRequest(id: number): Promise<LeaveRequest>;
  createRequest(d: LeaveDraft): Promise<LeaveRequest>;
  updateRequest(id: number, d: Partial<LeaveDraft>): Promise<LeaveRequest>;
  actRequest(id: number, action: string, reason?: string): Promise<LeaveRequest>;
  listComments(id: number): Promise<Comment[]>;
  addComment(id: number, body: string): Promise<Comment>;
  listAttachments(id: number): Promise<Attachment[]>;
  addAttachment(id: number, fileName: string): Promise<Attachment>;
  balances(year: number, employeeId?: number): Promise<Balance[]>;
  entitlements(year: number): Promise<Entitlement[]>;
  adjustEntitlement(id: number, days: string, reason: string): Promise<Entitlement>;
  importEntitlements(csv: string, dryRun: boolean): Promise<ImportPreview>;
  recordAbsence(d: LeaveDraft): Promise<LeaveRequest>;
  calendar(from: string, to: string, scope: "me" | "team" | "org"): Promise<CalendarEvent[]>;
  holidays(): Promise<Holiday[]>;
  saveHoliday(h: Omit<Holiday, "id"> & { id?: number }): Promise<Holiday>;
  deleteHoliday(id: number): Promise<void>;
  notifications(): Promise<NotificationItem[]>;
  readNotification(id: number): Promise<void>;
  employees(q?: string): Promise<Employee[]>;
  saveEmployee(e: Partial<Employee> & { displayName: string; personnelCode: string; companyId: number }): Promise<Employee>;
  companies(): Promise<Company[]>;
  departments(): Promise<Department[]>;
  saveCompany(c: Partial<Company> & { code: string; name: string }): Promise<Company>;
  saveDepartment(d: Partial<Department> & { code: string; name: string; companyId: number }): Promise<Department>;
  contracts(employeeId: number): Promise<ContractPeriod[]>;
  saveContract(p: Omit<ContractPeriod, "id"> & { id?: number }): Promise<ContractPeriod>;
  coverage(from: string, to: string): Promise<CoverageRow[]>;
  reports(kind: string): Promise<ReportSummary>;
  settings(): Promise<SettingItem[]>;
  saveSetting(key: string, value: unknown, reason: string): Promise<SettingItem>;
  jobs(): Promise<JobRow[]>;
  audit(): Promise<AuditRow[]>;
  health(): Promise<{ live: boolean; ready: boolean; db: string; lastJob: string }>;
  estimate(employeeId: number | null, start: string, end: string): Promise<{ days: number; estimated: true }>;
  clientPolicy(): Promise<ClientPolicy>;
  bradfordNotes(): Promise<BradfordNote[]>;
  saveBradfordNote(employeeId: number, body: string): Promise<BradfordNote>;
}
