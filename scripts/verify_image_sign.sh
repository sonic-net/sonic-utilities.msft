#!/bin/sh
image_file="${1}"
cms_sig_file="sig.cms"
lines_for_lookup=50
SECURE_UPGRADE_ENABLED=0
DIR="$(dirname "$0")"
if [ -d "/sys/firmware/efi/efivars" ]; then
    if ! [ -n "$(ls -A /sys/firmware/efi/efivars 2>/dev/null)" ]; then
        mount -t efivarfs none /sys/firmware/efi/efivars 2>/dev/null
    fi
    SECURE_UPGRADE_ENABLED=$(bootctl status 2>/dev/null | grep -c "Secure Boot: enabled")
else
    echo "efi not supported - exiting without verification"
    exit 0
fi

. /usr/local/bin/verify_image_sign_common.sh

if [ ${SECURE_UPGRADE_ENABLED} -eq 0 ]; then
    echo "secure boot not enabled - exiting without image verification"
    exit 0
fi

clean_up ()
{
    if  [ -d ${EFI_CERTS_DIR} ]; then rm -rf ${EFI_CERTS_DIR}; fi
    if  [ -d "${TMP_DIR}" ]; then rm -rf ${TMP_DIR}; fi
    exit $1
}

TMP_DIR=$(mktemp -d)
DATA_FILE="${TMP_DIR}/data.bin"
CMS_SIG_FILE="${TMP_DIR}/${cms_sig_file}"
TAR_SIZE=$(head -n $lines_for_lookup $image_file | grep "payload_image_size=" | cut -d"=" -f2- )
SHARCH_SIZE=$(sed '/^exit_marker$/q' $image_file | wc -c)
SIG_PAYLOAD_SIZE=$(($TAR_SIZE + $SHARCH_SIZE ))
# Extract cms signature from signed file
# Add extra byte for payload
sed -e '1,/^exit_marker$/d' $image_file | tail -c +$(( $TAR_SIZE + 1 )) > $CMS_SIG_FILE
# Extract image from signed file
head -c $SIG_PAYLOAD_SIZE $image_file > $DATA_FILE
# verify signature with certificate fetched with efi tools
EFI_CERTS_DIR=/tmp/efi_certs
[ -d $EFI_CERTS_DIR ] && rm  -rf $EFI_CERTS_DIR
mkdir $EFI_CERTS_DIR
efi-readvar -v db -o $EFI_CERTS_DIR/db_efi >/dev/null || 
{
    echo "Error: unable to read certs from efi db: $?"
    clean_up 1
}
# Convert one file to der certificates
sig-list-to-certs $EFI_CERTS_DIR/db_efi $EFI_CERTS_DIR/db >/dev/null||
{
    echo "Error: convert sig list to certs: $?"
    clean_up 1
}
for file in $(ls $EFI_CERTS_DIR | grep "db-"); do
    LOG=$(openssl  x509 -in $EFI_CERTS_DIR/$file -inform der -out $EFI_CERTS_DIR/cert.pem 2>&1)
    if [ $? -ne 0 ]; then
        logger "cms_validation: $LOG"
    fi
    # Verify detached signature
    LOG=$(verify_image_sign_common $image_file $DATA_FILE $CMS_SIG_FILE)
    VALIDATION_RES=$?
    if [ $VALIDATION_RES -eq 0 ]; then
        RESULT="CMS Verified OK using efi keys"
        echo "verification ok:$RESULT"
        # No need to continue.
        # Exit without error if any success signature verification.
        clean_up 0
    fi
done
echo "Failure: CMS signature Verification Failed: $LOG"

clean_up 1