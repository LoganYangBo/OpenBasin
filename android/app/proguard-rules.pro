# JavaMail (com.sun.mail:android-mail) relies on reflection over provider classes.
-keep class com.sun.mail.** { *; }
-keep class javax.mail.** { *; }
-dontwarn javax.activation.**
-dontwarn java.awt.**
