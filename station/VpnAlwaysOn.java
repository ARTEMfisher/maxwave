import android.os.IBinder;
import java.lang.reflect.Method;
import java.util.Collections;
public final class VpnAlwaysOn {
 public static void main(String[]args)throws Exception{
  IBinder binder=(IBinder)Class.forName("android.os.ServiceManager").getMethod("getService",String.class).invoke(null,"connectivity");
  Object api=Class.forName("android.net.IConnectivityManager$Stub").getMethod("asInterface",IBinder.class).invoke(null,binder);
  Class<?> iface=Class.forName("android.net.IConnectivityManager");
  for(Method m:iface.getMethods())if(m.getName().equals("isAlwaysOnVpnPackageSupported"))System.out.println("SUPPORTED="+m.invoke(api,0,"su.happ.proxyutility"));
  if(args.length>0&&args[0].equals("enable")){
   boolean called=false;
   for(Method m:iface.getMethods())if(m.getName().equals("setAlwaysOnVpnPackage")){
    Class<?>[]t=m.getParameterTypes();
    if(t.length==3){System.out.println("ENABLED="+m.invoke(api,0,"su.happ.proxyutility",false));called=true;break;}
    if(t.length==4&&java.util.List.class.isAssignableFrom(t[3])){System.out.println("ENABLED="+m.invoke(api,0,"su.happ.proxyutility",false,Collections.emptyList()));called=true;break;}
   }
   if(!called)throw new IllegalStateException("Unsupported platform API");
  }
  for(Method m:iface.getMethods())if(m.getName().equals("getAlwaysOnVpnPackage"))System.out.println("PACKAGE="+m.invoke(api,0));
 }
}
