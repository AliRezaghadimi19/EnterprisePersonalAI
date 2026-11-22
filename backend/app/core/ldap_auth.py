"""
Active Directory / LDAP Authentication Module
Features:
- Secure LDAP and LDAPS client
- Prevention of LDAP Injection by escaping search filter characters (RFC 4515)
- Support for Domain Controller validation, User Search Base, Group Mapping
- Connection testing
- Zero storage of Active Directory passwords
- Mock/Offline testing mode for development environments
"""

import re
import socket
import ssl
from typing import Dict, List, Optional, Tuple, Any

def escape_ldap_filter(user_input: str) -> str:
    r"""
    Escape special characters to prevent LDAP Injection according to RFC 4515.
    Special characters: \ * ( ) \x00
    """
    if not user_input:
        return ""
    
    # Replace backslash first to prevent double-escaping
    escaped = user_input.replace("\\", "\\5c")
    escaped = escaped.replace("*", "\\2a")
    escaped = escaped.replace("(", "\\28")
    escaped = escaped.replace(")", "\\29")
    escaped = escaped.replace("\x00", "\\00")
    escaped = escaped.replace("/", "\\2f")
    return escaped

class LDAPAuthenticator:
    """
    Manages connections to Microsoft Active Directory / LDAP servers.
    """
    def __init__(
        self,
        server_host: str,
        port: int = 389,
        use_ssl: bool = False,
        domain_name: Optional[str] = None,
        base_dn: Optional[str] = None,
        user_search_base: Optional[str] = None,
        group_search_base: Optional[str] = None,
        bind_dn: Optional[str] = None,
        bind_password: Optional[str] = None,
        allowed_groups: Optional[List[str]] = None,
        group_role_mapping: Optional[Dict[str, str]] = None,
        timeout: int = 5
    ):
        self.server_host = server_host
        self.port = port
        self.use_ssl = use_ssl
        self.domain_name = domain_name or ""
        self.base_dn = base_dn or ""
        self.user_search_base = user_search_base or self.base_dn
        self.group_search_base = group_search_base or self.base_dn
        self.bind_dn = bind_dn or ""
        self.bind_password = bind_password or ""
        self.allowed_groups = allowed_groups or []
        self.group_role_mapping = group_role_mapping or {}
        self.timeout = timeout

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test reachability and handshake with the Domain Controller.
        Returns (success: bool, message: str) in Persian.
        """
        if not self.server_host:
            return False, "آدرس کنترلر دامنه (Domain Controller) مشخص نشده است."
            
        # Development / Simulation hook for mock AD environments
        if self.server_host in ("ad.mock.local", "mock-ad"):
            return True, "ارتباط آزمایشی با کنترلر دامنه شبیه‌سازی‌شده با موفقیت برقرار شد."

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            if self.use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                secure_sock = context.wrap_socket(sock, server_hostname=self.server_host)
                secure_sock.connect((self.server_host, self.port))
                secure_sock.close()
            else:
                sock.connect((self.server_host, self.port))
                sock.close()
                
            return True, f"اتصال به اکتیو دایرکتوری در پورت {self.port} با موفقیت برقرار شد."
        except socket.timeout:
            return False, "خطای انقضای زمان: ارتباط با کنترلر دامنه در زمان مقرر برقرار نشد."
        except ConnectionRefusedError:
            return False, f"اتصال رد شد: هیچ سرویس LDAP فعالی در پورت {self.port} یافت نشد."
        except Exception as e:
            return False, f"خطا در برقراری ارتباط با اکتیو دایرکتوری: {str(e)}"

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Authenticate user credentials against Active Directory.
        Validates membership in allowed groups and returns user directory attributes.
        """
        if not username or not password:
            return False, None, "نام کاربری یا رمز عبور نباید خالی باشد."
            
        safe_username = escape_ldap_filter(username)
        
        # Mock mode for testing environments
        if self.server_host in ("ad.mock.local", "mock-ad"):
            if username == "ad_user" and password == "AD_Pass123!":
                user_info = {
                    "username": "ad_user",
                    "first_name": "کاربر",
                    "last_name": "سازمانی AD",
                    "email": "ad_user@enterprise.local",
                    "department": "فناوری اطلاعات",
                    "groups": ["IT-Staff", "Domain Users"],
                    "mapped_role": "مشترک فنی"
                }
                return True, user_info, "احراز هویت Active Directory با موفقیت انجام شد."
            elif username == "ad_forbidden":
                return False, None, "کاربر به گروه‌های مجاز سازمانی تعلق ندارد."
            else:
                return False, None, "اطلاعات کاربری در Active Directory نامعتبر است."

        # Production LDAP integration via ldap3 if available
        try:
            import ldap3
            server = ldap3.Server(
                self.server_host,
                port=self.port,
                use_ssl=self.use_ssl,
                connect_timeout=self.timeout
            )
            
            # Format User Principal Name or sAMAccountName
            user_dn = f"{safe_username}@{self.domain_name}" if self.domain_name else safe_username
            conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
            
            if not conn.bound:
                return False, None, "احراز هویت کاربر در اکتیو دایرکتوری ناموفق بود."
                
            # Search for user attributes and group memberships
            search_filter = f"(&(objectClass=user)(sAMAccountName={safe_username}))"
            conn.search(
                search_base=self.user_search_base or self.base_dn,
                search_filter=search_filter,
                attributes=['sAMAccountName', 'givenName', 'sn', 'mail', 'department', 'memberOf']
            )
            
            if not conn.entries:
                return False, None, "اطلاعات کاربر پس از ورود در پایگاه داده AD یافت نشد."
                
            entry = conn.entries[0]
            member_of = [str(g).split(',')[0].replace('CN=', '') for g in getattr(entry, 'memberOf', [])]
            
            # Group restriction check
            if self.allowed_groups:
                has_access = any(grp in self.allowed_groups for grp in member_of)
                if not has_access:
                    return False, None, "دسترسی کاربر به دلیل عدم عضویت در گروه‌های مجاز سازمان مسدود شده است."
                    
            # Map role
            mapped_role = "مشترک عادی"
            for grp, role in self.group_role_mapping.items():
                if grp in member_of:
                    mapped_role = role
                    break
                    
            user_data = {
                "username": safe_username,
                "first_name": str(getattr(entry, 'givenName', 'کاربر')),
                "last_name": str(getattr(entry, 'sn', 'سازمان')),
                "email": str(getattr(entry, 'mail', f"{safe_username}@{self.domain_name}")),
                "department": str(getattr(entry, 'department', 'سازمانی')),
                "groups": member_of,
                "mapped_role": mapped_role
            }
            conn.unbind()
            return True, user_data, "احراز هویت موفق با کنترلر دامنه."
        except ImportError:
            # Fallback if ldap3 library is not loaded on this host
            return False, None, "ماژول اتصال ldap3 بر روی سیستم نصب نیست."
        except Exception as e:
            return False, None, f"خطای ارتباط با سرور دایرکتوری: {str(e)}"
