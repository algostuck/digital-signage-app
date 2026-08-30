# Demo Credentials

> **Demo only.** Every account below belongs to a fictional demo tenant in
> a development database. These are not customer accounts, the passwords
> are deliberately public, and nothing here may be used in production.
> `app.demo_seed` refuses to run when `ENVIRONMENT=production`.

All demo users share one password:

```
Demo@12345
```

Passwords are stored hashed through the application's own hasher
(`app.core.security.hash_password`) — no plaintext is written to the
database.

## Platform (unchanged by the demo seeder)

| Account | Password | Purpose |
|---|---|---|
| `platform@signage.cloud` | `Platform@12345` | Super Admin — the `/platform` console, tenant onboarding, plan approvals |
| `admin@demo-org.com` | `Admin@12345` | The original `demo` fixture org; the automated test suite logs in as this user |

Both are preserved by the demo seeder and verified on every run.

## 1. Reliance Retail Digital Experience — `RRL-DEMO`

Enterprise plan · 130 displays · the primary demo tenant.

| Name | Email | Role |
|---|---|---|
| Arjun Mehta | `arjun.mehta@rrl-demo.signage.cloud` | Organization Administrator (owner) |
| Priya Sharma | `priya.sharma@rrl-demo.signage.cloud` | Content Manager |
| Rahul Sen | `rahul.sen@rrl-demo.signage.cloud` | Device Manager |
| Sneha Iyer | `sneha.iyer@rrl-demo.signage.cloud` | Campaign Approver *(custom role)* |
| Vikram Malhotra | `vikram.malhotra@rrl-demo.signage.cloud` | Regional Operations Manager *(custom role)* |
| Neha Kapoor | `neha.kapoor@rrl-demo.signage.cloud` | Report Viewer *(custom role)* |
| Amit Banerjee | `amit.banerjee@rrl-demo.signage.cloud` | Viewer |
| Rohan Nair | `rohan.nair@rrl-demo.signage.cloud` | Content Manager |
| Kavita Rao | `kavita.rao@rrl-demo.signage.cloud` | Device Manager |
| Sourav Mukherjee | `sourav.mukherjee@rrl-demo.signage.cloud` | Viewer |

## 2. BharatMart Retail Network — `BMR-DEMO`

Business plan · 88 displays — deliberately at **88% of the 100-device plan
limit** so the plan-usage UI has a near-limit tenant to show.

| Name | Email | Role |
|---|---|---|
| Rohan Nair | `rohan.nair@bharatmart-demo.signage.cloud` | Organization Administrator (owner) |
| Kavita Rao | `kavita.rao@bharatmart-demo.signage.cloud` | Content Manager |
| Sourav Mukherjee | `sourav.mukherjee@bharatmart-demo.signage.cloud` | Device Manager |
| Ananya Desai | `ananya.desai@bharatmart-demo.signage.cloud` | Campaign Approver |
| Karthik Subramanian | `karthik.subramanian@bharatmart-demo.signage.cloud` | Regional Operations Manager |
| Meera Joshi | `meera.joshi@bharatmart-demo.signage.cloud` | Report Viewer |

## 3. UrbanSquare Properties — `USP-DEMO`

Professional plan · 40 displays · commercial property portfolio
(lobbies, towers, amenity decks rather than retail stores).

| Name | Email | Role |
|---|---|---|
| Divya Pillai | `divya.pillai@urbansquare-demo.signage.cloud` | Organization Administrator (owner) |
| Rajesh Gupta | `rajesh.gupta@urbansquare-demo.signage.cloud` | Content Manager |
| Shalini Reddy | `shalini.reddy@urbansquare-demo.signage.cloud` | Device Manager |
| Nikhil Chatterjee | `nikhil.chatterjee@urbansquare-demo.signage.cloud` | Campaign Approver |
| Pooja Bhatt | `pooja.bhatt@urbansquare-demo.signage.cloud` | Regional Operations Manager |

> The same fictional person may appear in more than one tenant with a
> different role — each is a separate user record scoped to its own
> organization, which is what the platform's `(organization_id, email)`
> uniqueness models.

## Multi-tenant user (tenant switching)

**Vikram Malhotra** — `vikram.malhotra@rrl-demo.signage.cloud` — is the
one account with access to two tenants:

| Tenant | Access |
|---|---|
| Reliance Retail Digital Experience | home · Regional Operations Manager |
| BharatMart Retail Network | guest · Viewer |

Sign in as Vikram to demonstrate the header's tenant switcher: the data
changes completely on switch, and his **guest role is enforced** in the
second tenant (he can read BharatMart but cannot create campaigns there).

## Suggested demo path

1. Sign in as **Arjun Mehta** → Dashboard shows ~108/130 online with a
   real health mix.
2. **Locations** → India → Maharashtra → Mumbai → Andheri → store → zone
   (six levels of real Indian geography).
3. **Devices** → filter, group, inspect a display's health.
4. **Content** → folder tree, real thumbnails, published/draft states.
5. **Campaigns** → mixed lifecycle; open one to see targeting and schedule.
6. **Reports** → proof-of-play built from ~13.8k playback events.
7. **Settings → Plan & usage** → Enterprise entitlements and live usage.
8. Sign in as **Amit Banerjee** (Viewer) to show RBAC hiding actions.
9. Sign in as **Rohan Nair** (BharatMart) to show tenant isolation and a
   different plan's feature set.
