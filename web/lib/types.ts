export interface GitHubFactors {
  account_age_days: number;
  min_account_age_days: number;
  passed_age: boolean;
  public_repos: number;
  min_public_repos: number;
  passed_repos: boolean;
  followers: number;
  following: number;
  profile_complete: boolean;
  has_name?: boolean;
  has_bio?: boolean;
  days_since_update?: number;
  account_type?: string;
}

export interface RegisterRequestPayload {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  password?: string;
  githubUsername: string;
  workerName: string;
}

export interface RegisterResponse {
  status: "pending_otp" | "error";
  session_id?: string;
  worker_name?: string;
  github_username?: string;
  email?: string;
  github_score?: number;
  factors?: GitHubFactors;
  message?: string;
  dev_mode?: boolean;
  dev_otp?: string;
  detail?: string | {
    message?: string;
    reasons?: string[];
    factors?: GitHubFactors;
    score?: number;
  };
}

export interface VerifyOtpPayload {
  session_id: string;
  otp: string;
}

export interface VerifyOtpResponse {
  status: "authenticated" | "error";
  worker_id?: string;
  worker_name?: string;
  github_username?: string;
  worker_token?: string;
  message?: string;
  detail?: string;
}

export interface CoordinatorStats {
  tasks: {
    pending?: number;
    done?: number;
    invalid?: number;
    [key: string]: number | undefined;
  };
  workers: Array<{
    id?: string;
    name: string;
    github_username?: string;
    email?: string;
    status?: string;
    credits: number;
    online: boolean;
    running: number;
  }>;
  jobs: Array<{
    id: number;
    kind: string;
    total: number;
    done: number;
    seconds?: number;
    pi?: number;
  }>;
}

